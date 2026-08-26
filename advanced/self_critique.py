# Self-Critique Loop (self_critique.py)
CRITIQUE_PROMPT = """Review the following response to a task and identify
any weaknesses, errors, or omissions. Be specific and constructive.
If the response is already excellent and needs no improvement, reply with
exactly: NO_IMPROVEMENTS_NEEDED

Task: {task}
Response: {response}

Critique:"""

REFINE_PROMPT = """Revise the following response to address these critiques.
Produce an improved version only — no meta-commentary.

Task: {task}
Original response: {response}
Critiques: {critique}

Improved response:"""


class SelfCritiqueLoop:
    """
    Runs iterative self-critique and refinement on an agent answer.
    Stops early if the LLM reports no improvements are needed.
    """

    def __init__(self, backend):
        self.backend = backend

    def run(self, task: str, initial_answer: str, max_rounds: int = 3) -> str:
        answer = initial_answer

        for round_num in range(1, max_rounds + 1):
            # Step 1: Ask LLM to critique the current answer
            critique_prompt = CRITIQUE_PROMPT.format(task=task, response=answer)
            critique = self.backend.chat(
                [{"role": "user", "content": critique_prompt}]
            )

            # Step 2: If LLM says no improvements needed, stop
            if "NO_IMPROVEMENTS_NEEDED" in critique.upper():
                print(f"[SelfCritique] No improvements needed after round {round_num}.")
                break

            print(f"[SelfCritique] Round {round_num} critique: {critique[:100]}...")

            # Step 3: Ask LLM to produce a refined answer
            refine_prompt = REFINE_PROMPT.format(
                task=task, response=answer, critique=critique
            )
            answer = self.backend.chat(
                [{"role": "user", "content": refine_prompt}]
            )

        return answer
    