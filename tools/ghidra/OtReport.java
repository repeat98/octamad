// Prints what analysis made of a program: functions, instructions, and the
// disassembly errors Ghidra bookmarked.  analyzeHeadless's -postScript.
//
// DEBUG set in the environment lists each error bookmark.
//@category octabam
import java.util.Iterator;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.BookmarkType;

public class OtReport extends GhidraScript {

	@Override
	public void run() throws Exception {
		boolean debug = System.getenv("DEBUG") != null && !System.getenv("DEBUG").isEmpty();
		int funcs = currentProgram.getFunctionManager().getFunctionCount();
		long insns = currentProgram.getListing().getNumInstructions();
		int errors = 0;
		Iterator<Bookmark> it =
			currentProgram.getBookmarkManager().getBookmarksIterator(BookmarkType.ERROR);
		while (it.hasNext()) {
			Bookmark b = it.next();
			errors++;
			if (debug) {
				println("OtReport> " + b.getAddress() + " " + b.getCategory() + ": " + b.getComment());
			}
		}
		println(String.format("OtReport: %s: %d functions, %d instructions, %d error bookmarks",
			currentProgram.getName(), funcs, insns, errors));
	}
}
