import json, re
from pathlib import Path
from template import RAGASEvaluator, BenchmarkRunner, FailureAnalyzer, QAPair

golden = json.loads(Path("golden_dataset.json").read_text(encoding="utf-8"))
actual = json.loads(Path("artifacts/actual_answers.json").read_text(encoding="utf-8"))
actual_by_id = {r["id"]: r for r in actual["answers"]}

qa_pairs=[]
for rec in golden["qa_pairs"]:
    rid=rec["id"]
    ar=actual_by_id[rid]
    gold_texts=[c["text"].strip() for c in rec["contexts"]]
    ret_texts=[c["text"].strip() for c in ar["retrieved_contexts"]]
    qa_pairs.append(QAPair(
        question=rec["question"], expected_answer=rec["expected_answer"],
        context="\n\n".join(gold_texts),
        metadata={"id":rid,"difficulty":rec["difficulty"],"attack_type":rec["attack_type"]},
        retrieved_contexts=ret_texts
    ))

answers_by_q={r["question"]: r["actual_answer"] for r in actual["answers"]}
def agent_fn(q): return answers_by_q[q]

ev=RAGASEvaluator()
runner=BenchmarkRunner()
results=runner.run(qa_pairs, agent_fn, ev)
summary=runner.generate_report(results)

# Save benchmark_results.json like evaluate_answers.py does
from evaluate_answers import build_evaluation_artifact
import json as _json
artifact=build_evaluation_artifact(results, summary, FailureAnalyzer())
Path("artifacts/benchmark_results.json").write_text(_json.dumps(artifact, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("Saved artifacts/benchmark_results.json\n")

# Print Exercise 3.2 table
def fmt(v): return "n/a" if v is None else f"{v:.3f}"
print("| ID | Question (short) | Ctx Recall | Ctx Precision | Faithfulness | Relevance | Completeness | Overall | Passed? | Failure Type |")
print("|----|------------------|------------|---------------|--------------|-----------|--------------|---------|---------|--------------|")
for r in results:
    q=re.sub(r"\s+"," ",r.qa_pair.question).replace("|","\\|")
    if len(q)>48: q=q[:45]+"..."
    print(f"| {r.qa_pair.metadata['id']} | {q} | {fmt(r.context_recall)} | {fmt(r.context_precision)} | {r.faithfulness:.3f} | {r.relevance:.3f} | {r.completeness:.3f} | {r.overall_score():.3f} | {'Yes' if r.passed else 'No'} | {r.failure_type or '-'} |")

print("\nAggregate Report:")
print(f"- Overall pass rate: {summary['pass_rate']:.1%}")
print(f"- Avg Context Recall: {fmt(summary['avg_context_recall'])}")
print(f"- Avg Context Precision: {fmt(summary['avg_context_precision'])}")
print(f"- Avg Faithfulness: {summary['avg_faithfulness']:.3f}")
print(f"- Avg Relevance: {summary['avg_relevance']:.3f}")
print(f"- Avg Completeness: {summary['avg_completeness']:.3f}")
print(f"- Failure type distribution: {summary['failure_types']}")

worst=sorted(results, key=lambda r: r.overall_score())[:3]
print("\n3 lowest-scoring cases:")
for i,r in enumerate(worst,1):
    print(f"{i}. ID: {r.qa_pair.metadata['id']} | Score: {r.overall_score():.3f} | Failure type: {r.failure_type or '-'} | Faith={r.faithfulness:.3f} Rel={r.relevance:.3f} Comp={r.completeness:.3f} | Recall={fmt(r.context_recall)} Prec={fmt(r.context_precision)}")

print("\n--- Per-case detail ---")
for r in results:
    print(f"{r.qa_pair.metadata['id']}: actual_answer=\"{r.actual_answer[:120]}...\"")
