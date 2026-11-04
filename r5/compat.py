"""Compatibility for older Qiskit bases, applied before any frozen code is imported. Qiskit 1.1 and 1.2 export
generate_preset_pass_manager only from qiskit.transpiler.preset_passmanagers; the frozen R4 and cart code import it
from qiskit.transpiler. The shim adds the same function under the newer name and changes nothing else."""
import qiskit.transpiler as _T

if not hasattr(_T, "generate_preset_pass_manager"):
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager as _g
    _T.generate_preset_pass_manager = _g
