"""Debug script to trace why gaps don't appear in a real AIE interview."""
import sys, json
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Start AIE session
resp = client.post("/api/expert/sessions", json={"domain": "AIE"})
sid = resp.json()["session_id"]
print(f"Session: {sid}")

# Answer all questions to finish
for i in range(25):
    q_resp = client.get(f"/api/expert/sessions/{sid}/question").json()
    if q_resp["finished"]:
        print(f"  Finished after {i} questions")
        break
    q = q_resp["question"]
    qt = q["type"]
    fk = q["fact_key"]
    
    if qt == "boolean":
        ans = True
    elif qt == "scale":
        ans = 1  # low → gap trigger
    elif qt == "numeric":
        ans = 4  # low hours → gap trigger
    elif qt == "choice":
        choices = q.get("choices_en", [])
        ans = choices[0] if choices else "internship"
    elif qt == "multi_choice":
        choices = q.get("choices_en", [])
        ans = [choices[0]] if choices else ["option1"]
    else:
        ans = "test"
    
    a_resp = client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": ans}).json()
    print(f"  Q{i+1}: {fk} ({qt}) = {ans} -> next={a_resp.get('next_node')} finished={a_resp.get('is_finished')}")

# Get final result
result = client.get(f"/api/expert/sessions/{sid}/result").json()

print()
print("=== RESULT ===")
print(f"selected_goal: {result.get('selected_goal')}")
print(f"fit_score: {result.get('fit_score')}")
print(f"gaps ({len(result.get('gaps', []))}): {result.get('gaps')}")
print(f"strengths ({len(result.get('strengths', []))}): {result.get('strengths')}")
print(f"next_steps ({len(result.get('next_steps', []))}): {result.get('next_steps')}")
print(f"why_selected ({len(result.get('why_selected', []))}): {result.get('why_selected')}")

# Check state for final_output
state = client.get(f"/api/expert/sessions/{sid}/state").json()
fo = state.get("final_output")
if fo:
    print(f"\nfinal_output top_goal: {fo.get('top_goal', {}).get('goal_id') if fo.get('top_goal') else 'NONE'}")
    print(f"final_output gaps: {fo.get('gaps')}")
else:
    print("\nfinal_output is None!")
