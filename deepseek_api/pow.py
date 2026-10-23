import base64
import json
from typing import Any, Dict, Optional


class PowSolver:
    """Solves DeepSeek Proof-of-Work (PoW) challenges using WASM / deepseek-pow."""

    def __init__(self):
        self._solver = None

    def _get_solver(self, algorithm: str):
        try:
            from deepseek_pow import registry
            return registry.get(algorithm)
        except Exception as e:
            print(f"[PoW Warning] Could not load solver for {algorithm}: {e}")
            return None

    def solve_challenge(self, challenge_data: Dict[str, Any], target_path: str = "/api/v0/chat/completion") -> Optional[str]:
        """
        Solves the given challenge and returns base64 encoded string for `x-ds-pow-response` header.
        """
        algorithm = challenge_data.get("algorithm", "DeepSeekHashV1")
        solver = self._get_solver(algorithm)
        if not solver:
            return None

        try:
            from deepseek_pow import Challenge

            # Map fields
            challenge_obj = Challenge(
                algorithm=algorithm,
                challenge=challenge_data["challenge"],
                salt=challenge_data["salt"],
                difficulty=challenge_data["difficulty"],
                expire_at=challenge_data["expire_at"],
                signature=challenge_data.get("signature")
            )

            solution = solver.solve(challenge_obj)
            payload = solution.to_answer_payload()
            payload["target_path"] = target_path

            raw_json = json.dumps(payload, separators=(',', ':'))
            encoded = base64.b64encode(raw_json.encode('utf-8')).decode('utf-8')
            return encoded
        except Exception as e:
            print(f"[PoW Error] Failed solving challenge: {e}")
            return None


default_pow_solver = PowSolver()
