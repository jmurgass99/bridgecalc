// bridgeSolver.cpp — C++ WebAssembly kernel for AASHTO HL-93 / EN 1991-2 LM1
// continuous bridge envelope evaluation.

extern "C" {

double hl93SimpleSpanMoment(double L, double impact) {
    return impact * (90.0 * L) + 1.1625 * L * L;
}

double beamFlexuralStiffness(double E, double I, double L) {
    return (12.0 * E * I) / (L * L * L);
}

}
