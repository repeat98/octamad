/* ###
 * IP: GHIDRA
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package ghidra.app.plugin.core.analysis;

import java.math.BigInteger;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.services.*;
import ghidra.app.util.importer.MessageLog;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Marks the last instruction of a DSP56300 hardware loop when it is a two-word instruction.
 * <p>
 * DO and DOR name the loop's last <i>word</i> (LA).  The SLEIGH specification attaches the
 * loop-back to the instruction at LA through context set by the DO instruction.  When the
 * last instruction of the loop is two words long it starts at LA-1, the context lands in the
 * middle of it, and the loop-back is lost.  This analyzer finds those loops, moves the
 * loop-end context to LA-1 and re-disassembles that instruction.
 */
public class DSP56300LoopEndAnalyzer extends AbstractAnalyzer {

	private static final String NAME = "DSP56300 Loop End";
	private static final String DESCRIPTION =
		"Attaches DO/DOR loop-back semantics to a hardware loop whose last instruction " +
			"is a two-word instruction.";

	public DSP56300LoopEndAnalyzer() {
		super(NAME, DESCRIPTION, AnalyzerType.INSTRUCTION_ANALYZER);
		setPriority(AnalysisPriority.DISASSEMBLY.after());
		setDefaultEnablement(true);
		setSupportsOneTimeAnalysis();
	}

	@Override
	public boolean canAnalyze(Program program) {
		return "DSP56300".equals(program.getLanguage().getProcessor().toString());
	}

	@Override
	public boolean added(Program program, AddressSetView set, TaskMonitor monitor,
			MessageLog log) throws CancelledException {
		Register lbot = program.getRegister("lbot");
		Register lfor = program.getRegister("lfor");
		Register ltop = program.getRegister("ltop");
		Listing listing = program.getListing();
		InstructionIterator it = listing.getInstructions(set, true);
		while (it.hasNext()) {
			monitor.checkCancelled();
			Instruction ins = it.next();
			String mnemonic = ins.getMnemonicString();
			if (!mnemonic.equals("do") && !mnemonic.equals("dor")) {
				continue;
			}
			try {
				fixLoopEnd(program, ins, mnemonic.equals("dor"), lbot, lfor, ltop, monitor);
			}
			catch (MemoryAccessException | ghidra.program.model.listing.ContextChangeException e) {
				log.appendMsg(NAME, "Could not fix loop end for " + ins.getAddress() + ": " +
					e.getMessage());
			}
		}
		return true;
	}

	private void fixLoopEnd(Program program, Instruction doIns, boolean relative, Register lbot,
			Register lfor, Register ltop, TaskMonitor monitor)
			throws MemoryAccessException, ContextChangeException {
		AddressSpace space = doIns.getAddress().getAddressSpace();
		int unit = space.getAddressableUnitSize();
		if (doIns.getLength() != 2 * unit) {
			return;
		}
		byte[] ext = new byte[unit];
		doIns.getBytes(ext, unit);	// second word: LA, or LA's displacement for DOR
		long value = (ext[0] & 0xffL) | ((ext[1] & 0xffL) << 8) | ((ext[2] & 0xffL) << 16);
		long doWord = doIns.getAddress().getAddressableWordOffset();
		long la = value;
		if (relative) {
			la = (doWord + ((value << 40) >> 40)) & 0xffffffL;	// sign-extend the 24-bit displacement
		}
		Address laAddr = space.getTruncatedAddress(la, true);
		Listing listing = program.getListing();
		Instruction last = listing.getInstructionContaining(laAddr);
		if (last == null || last.getMinAddress().equals(laAddr)) {
			return;		// nothing there yet, or the SLEIGH context already applies
		}
		Address start = last.getMinAddress();
		Address end = last.getMaxAddress();
		boolean forever = doIns.toString().contains("forever");
		listing.clearCodeUnits(start, end, false);
		ProgramContext ctx = program.getProgramContext();
		ctx.setValue(lbot, start, start, BigInteger.ONE);
		ctx.setValue(lfor, start, start, forever ? BigInteger.ONE : BigInteger.ZERO);
		ctx.setValue(ltop, start, start, BigInteger.valueOf(doWord + 2));
		DisassembleCommand cmd = new DisassembleCommand(start, new AddressSet(start, end), false);
		cmd.applyTo(program, monitor);
	}
}
