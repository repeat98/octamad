"""Stock effects plus the experimental analysis loop optimization."""
from remix.schema import Remix

REMIX = Remix(
    name="stock-analysis-fast",
    doc="Stock effects with a behavior-preserving CPU analysis-loop candidate.",
    modules=("STOCK ANALYSIS FAST", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
