// Applies an octabam layout file (tools/ghidra/ot_ghidra.py writes them) to the
// program being imported: memory blocks, labels, functions, data, references,
// comments.  Run as analyzeHeadless's -preScript, with the layout path as its
// argument, so the auto-analysis that follows starts from the right memory map.
//
// One directive per line; ADDR is SPACE:0xWORD (a word address in that space,
// so P:0x215 is the 0x215th DSP word; ram:0x40000400 on the ColdFire). FLAGS
// is any of r w x v (volatile). Paths are relative to the layout file.
//
//   rename  ADDR NAME FLAGS            the loader's block holding ADDR
//   file    NAME ADDR PATH FLAGS       initialized block from a file
//   block   NAME ADDR WORDS FLAGS      uninitialized block
//   alias   NAME ADDR TARGET WORDS FLAGS   byte-mapped onto TARGET (any space)
//   label   ADDR NAME                  the first label at ADDR becomes primary
//   code    ADDR NAME                  disassemble and label, no function
//   func    ADDR NAME                  disassemble and create (or rename) a function
//   entry   ADDR                       external entry point
//   data    ADDR TYPE COUNT            TYPE byte | uint3 (a 24-bit word); COUNT > 1 is an array
//   ref     ADDR TARGET                data reference
//   comment ADDR KIND TEXT...          KIND plate | pre | eol | repeatable
//
// DEBUG set in the environment prints every directive.
//@category octabam
import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.data.ArrayDataType;
import ghidra.program.model.data.ByteDataType;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.UnsignedInteger3DataType;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.data.DataUtilities;

public class OtLayout extends GhidraScript {

	private boolean debug;
	private int blocks, labels, funcs, datas, refs, comments, warnings;

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length != 1) {
			printerr("OtLayout: usage: OtLayout.java <layout file>");
			return;
		}
		debug = System.getenv("DEBUG") != null && !System.getenv("DEBUG").isEmpty();
		File layout = new File(args[0]);
		List<String> lines = Files.readAllLines(layout.toPath());
		int n = 0;
		for (String line : lines) {
			n++;
			line = line.strip();
			if (line.isEmpty() || line.startsWith("#")) {
				continue;
			}
			if (debug) {
				println("OtLayout> " + line);
			}
			try {
				apply(layout.getParentFile(), line);
			}
			catch (Exception e) {
				warnings++;
				printerr("OtLayout: " + layout.getName() + ":" + n + ": " + line + ": " + e);
			}
		}
		println(String.format(
			"OtLayout: %s: %d blocks, %d labels, %d functions, %d data, %d refs, %d comments, %d warnings",
			currentProgram.getName(), blocks, labels, funcs, datas, refs, comments, warnings));
	}

	private void apply(File dir, String line) throws Exception {
		String[] t = line.split("\\s+");
		Memory mem = currentProgram.getMemory();
		switch (t[0]) {
			case "rename": {
				MemoryBlock b = mem.getBlock(addr(t[1]));
				if (b == null) {
					throw new IllegalArgumentException("no block");
				}
				b.setName(t[2]);
				flags(b, t[3]);
				blocks++;
				break;
			}
			case "file": {
				File f = new File(dir, t[3]);
				try (InputStream in = new BufferedInputStream(new FileInputStream(f))) {
					MemoryBlock b = mem.createInitializedBlock(t[1], addr(t[2]), in, f.length(),
						monitor, false);
					flags(b, t[4]);
				}
				blocks++;
				break;
			}
			case "block": {
				Address a = addr(t[2]);
				MemoryBlock b = mem.createUninitializedBlock(t[1], a, words(a, t[3]), false);
				flags(b, t[4]);
				blocks++;
				break;
			}
			case "alias": {
				Address a = addr(t[2]);
				MemoryBlock b =
					mem.createByteMappedBlock(t[1], a, addr(t[3]), words(a, t[4]), false);
				flags(b, t[5]);
				blocks++;
				break;
			}
			case "label":
				label(addr(t[1]), t[2]);
				break;
			case "code": {
				Address a = addr(t[1]);
				disassemble(a);
				label(a, t[2]);
				break;
			}
			case "func": {
				Address a = addr(t[1]);
				disassemble(a);
				Function f = getFunctionAt(a);
				if (f == null) {
					f = createFunction(a, t[2]);
				}
				if (f == null) {
					throw new IllegalStateException("could not create a function");
				}
				f.setName(t[2], SourceType.IMPORTED);
				funcs++;
				break;
			}
			case "entry":
				currentProgram.getSymbolTable().addExternalEntryPoint(addr(t[1]));
				break;
			case "data": {
				Address a = addr(t[1]);
				DataType dt = switch (t[2]) {
					case "byte" -> ByteDataType.dataType;
					case "uint3" -> UnsignedInteger3DataType.dataType;
					default -> throw new IllegalArgumentException("unknown type " + t[2]);
				};
				int count = Integer.decode(t[3]);
				if (count > 1) {
					dt = new ArrayDataType(dt, count, dt.getLength());
				}
				DataUtilities.createData(currentProgram, a, dt, dt.getLength(), false,
					DataUtilities.ClearDataMode.CLEAR_ALL_UNDEFINED_CONFLICT_DATA);
				datas++;
				break;
			}
			case "ref":
				currentProgram.getReferenceManager()
						.addMemoryReference(addr(t[1]), addr(t[2]), RefType.DATA,
							SourceType.IMPORTED, 0);
				refs++;
				break;
			case "comment": {
				String text = line.split("\\s+", 4)[3];
				int kind = switch (t[2]) {
					case "plate" -> CodeUnit.PLATE_COMMENT;
					case "pre" -> CodeUnit.PRE_COMMENT;
					case "eol" -> CodeUnit.EOL_COMMENT;
					case "repeatable" -> CodeUnit.REPEATABLE_COMMENT;
					default -> throw new IllegalArgumentException("unknown comment kind " + t[2]);
				};
				Address a = addr(t[1]);
				String old = currentProgram.getListing().getComment(kind, a);
				currentProgram.getListing()
						.setComment(a, kind, old == null ? text : old + "\n" + text);
				comments++;
				break;
			}
			default:
				throw new IllegalArgumentException("unknown directive");
		}
	}

	/** SPACE:0xWORD -> address; the offset counts the space's addressable units. */
	private Address addr(String s) {
		int colon = s.indexOf(':');
		AddressSpace sp = colon < 0 ? currentProgram.getAddressFactory().getDefaultAddressSpace()
				: currentProgram.getAddressFactory().getAddressSpace(s.substring(0, colon));
		if (sp == null) {
			throw new IllegalArgumentException("no address space in " + s);
		}
		long off = Long.decode(s.substring(colon + 1));
		return sp.getTruncatedAddress(off, true);
	}

	/** A length in words -> bytes, for the space holding a. */
	private long words(Address a, String s) {
		return Long.decode(s) * a.getAddressSpace().getAddressableUnitSize();
	}

	private void flags(MemoryBlock b, String f) {
		b.setRead(f.contains("r"));
		b.setWrite(f.contains("w"));
		b.setExecute(f.contains("x"));
		b.setVolatile(f.contains("v"));
	}

	private void label(Address a, String name) throws Exception {
		SymbolTable st = currentProgram.getSymbolTable();
		for (Symbol s : st.getSymbols(a)) {
			if (s.getName().equals(name)) {
				return;
			}
		}
		st.createLabel(a, name, SourceType.IMPORTED);
		labels++;
	}
}
