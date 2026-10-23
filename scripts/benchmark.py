"""
scripts/benchmark.py
====================
Phase 4: Measure extraction performance on the development machine.

Benchmarks:
  1. Document text extraction time (DocumentReader)
  2. AI inference time per resume (AIExtractor)
  3. Full pipeline time per resume (DocumentReader → Parser → Validator)
  4. Batch processing time for N resumes

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --short-only      # 5 short resumes only
    python scripts/benchmark.py --runs 3          # repeat each N times
    python scripts/benchmark.py --output-dir bench_results/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ai_extractor import AIConfig, AIExtractor, check_ollama_running, check_model_available
from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus
from src.resume_parser import ResumeParser
from src.validator import validate_candidate

# ---------------------------------------------------------------------------
# Test texts of varying lengths
# ---------------------------------------------------------------------------

_SHORT_RESUME = """\
Jane Doe
jane.doe@example.com | +1-555-0101 | San Francisco, CA
https://linkedin.com/in/janedoe | https://github.com/janedoe

EDUCATION
B.Sc. Computer Science — State University, 2021

SKILLS
Python, SQL, Machine Learning, scikit-learn

EXPERIENCE
Data Scientist — DataCo (Jun 2021 – Present)
  • Built recommendation models.

PROJECTS
ChurnPredictor — Customer churn prediction (Python, scikit-learn)

CERTIFICATIONS
Google Data Analytics Certificate (2022)
"""

_MEDIUM_RESUME = """\
Carlos Martinez
carlos.martinez@techco.com | +52-55-5555-0144 | Mexico City, Mexico
https://linkedin.com/in/carlosmartinez | https://github.com/carlosmartinez

EDUCATION
M.Sc. Software Engineering — UNAM, 2018
B.Sc. Computer Science — Tecnológico de Monterrey, 2016

SKILLS
Python, JavaScript, TypeScript, React, Node.js, PostgreSQL, Redis, Docker, Kubernetes

EXPERIENCE
Senior Software Engineer — MexTech (Jan 2021 – Present)
  • Led migration of legacy monolith to microservices architecture.
  • Reduced API response time by 60% through caching and query optimization.
  • Mentored 4 junior engineers.

Software Engineer — StartupMX (Mar 2018 – Dec 2020)
  • Built full-stack e-commerce platform serving 50,000 users.
  • Implemented payment processing with Stripe integration.
  • Maintained 99.9% uptime for critical services.

Junior Developer — WebAgencyMX (Jun 2016 – Feb 2018)
  • Developed WordPress and React-based client websites.
  • Integrated third-party APIs for social media and analytics.

PROJECTS
EcommercePlatform — Full-stack e-commerce (React, Node.js, PostgreSQL, Redis)
ChatBot — Customer support chatbot (Python, NLP, FastAPI)
InventoryManager — Warehouse management system (TypeScript, Angular, MySQL)

CERTIFICATIONS
AWS Certified Developer Associate (2022)
Kubernetes Application Developer (CKAD) (2021)
Docker Certified Associate (2020)
"""

_LONG_RESUME = """\
Dr. Priya Krishnamurthy
p.krishnamurthy@deepresearch.edu | +91-98765-43210 | Bengaluru, India
https://linkedin.com/in/priyakrishnamurthy | https://github.com/priyak-ml
https://priyakrishnamurthy.dev

SUMMARY
Principal Research Scientist with 12+ years of experience in machine learning,
computer vision and natural language processing. Published 28 peer-reviewed
papers. Led research teams of up to 15 scientists. Holder of 4 patents.

EDUCATION
Ph.D. Computer Science (Machine Learning) — IISc Bangalore, 2012
M.Tech. Artificial Intelligence — IIT Madras, 2008
B.Tech. Computer Science — NIT Warangal, 2006

RESEARCH AREAS
Deep Learning, Computer Vision, NLP, Reinforcement Learning, Federated Learning,
Graph Neural Networks, Generative Models, Foundation Models, Multi-Modal Learning

TECHNICAL SKILLS
Python, C++, Java, MATLAB, R, Julia
TensorFlow, PyTorch, JAX, Keras, MXNet
OpenCV, PIL, scikit-image, SimpleITK
NLTK, spaCy, HuggingFace Transformers, Gensim
Spark, Hadoop, Flink, Kafka
AWS SageMaker, GCP Vertex AI, Azure ML
Docker, Kubernetes, Terraform, MLflow, DVC, Weights & Biases
CUDA, cuDNN, TensorRT, ONNX

EXPERIENCE
Principal Research Scientist — DeepResearch India (Apr 2020 – Present)
  • Leading a 15-person research team on foundation model pre-training.
  • Developed novel attention mechanism reducing compute by 35%.
  • Published 8 papers at top venues (NeurIPS, ICML, ICCV, ACL).
  • Secured $2.8M research grant from DST India.
  • Filed 2 patents on efficient transformer architectures.

Senior Research Scientist — AI Lab (Jan 2016 – Mar 2020)
  • Research on medical image segmentation using GANs.
  • Led team of 8 in building federated learning infrastructure.
  • Collaborated with 5 hospital partners across India.
  • Published 12 papers, 3 oral presentations at major conferences.
  • Filed 2 patents on privacy-preserving ML techniques.

Research Scientist — StartupAI (Jun 2013 – Dec 2015)
  • Built NLP pipeline for multilingual document classification.
  • Reduced inference latency by 70% through model distillation.
  • Deployed systems handling 10M+ documents per day.

Postdoctoral Researcher — IISc Bangalore (Jan 2012 – May 2013)
  • Research on sparse coding and dictionary learning.
  • Developed GPU-accelerated optimization algorithms.

SELECTED PUBLICATIONS
1. "Efficient Attention via Sparse Routing", NeurIPS 2023
2. "Federated Learning for Medical Imaging", Nature Machine Intelligence 2022
3. "Zero-Shot Cross-Lingual Transfer with Adapters", ACL 2021
4. "Graph Neural Networks for Molecular Property Prediction", ICML 2021
5. "Privacy-Preserving Federated Averaging", ICLR 2020

PROJECTS
MedSeg — Medical image segmentation framework (PyTorch, MONAI, ITK)
FedLearnLib — Federated learning library (Python, gRPC, Flower)
MultiLingNLP — Multilingual NLP toolkit (Python, HuggingFace, FastAPI)
SparseAttn — Efficient sparse attention implementation (CUDA, C++, Python)

CERTIFICATIONS
Google Cloud Professional Machine Learning Engineer (2023)
AWS Machine Learning Specialty (2022)
TensorFlow Developer Certificate (2021)
NVIDIA Deep Learning Institute: Multi-GPU Programming (2020)
Certified Kubernetes Administrator (CKA) (2019)
"""


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------

def _time_it(fn, runs: int = 1):
    """Run fn() `runs` times, return (results, durations_list)."""
    results = []
    durations = []
    for _ in range(runs):
        t0 = time.monotonic()
        r = fn()
        dt = time.monotonic() - t0
        results.append(r)
        durations.append(dt)
    return results[-1], durations


def _make_doc(text: str, name: str) -> DocumentResult:
    return DocumentResult(
        filename=name,
        status=ProcessingStatus.SUCCESS,
        text=text,
        file_hash=name,
    )


def bench_reader(runs: int = 5) -> dict:
    """Benchmark PDF bytes extraction (using the sample resumes directory)."""
    reader = DocumentReader()
    sample_dir = _ROOT / "sample_resumes"
    pdfs = list(sample_dir.glob("*.pdf"))
    docxs = list(sample_dir.glob("*.docx"))
    files = pdfs + docxs

    results = {}
    if not files:
        return {"note": "No sample_resumes files found — skipping reader benchmark"}

    for fp in files[:3]:  # limit to 3 files
        raw = fp.read_bytes()
        _, durs = _time_it(lambda b=raw, n=fp.name: reader.process_bytes(b, n), runs=runs)
        results[fp.name] = {
            "runs": runs,
            "mean_s": round(mean(durs), 3),
            "min_s": round(min(durs), 3),
            "max_s": round(max(durs), 3),
            "stdev_s": round(stdev(durs), 3) if runs > 1 else 0.0,
            "size_kb": round(len(raw) / 1024, 1),
        }

    return results


def bench_inference(extractor: AIExtractor, runs: int = 1) -> dict:
    """Benchmark AI inference on short, medium and long resumes."""
    cases = [
        ("short (~300 chars)",  _SHORT_RESUME[:300]),
        ("short (full)",        _SHORT_RESUME),
        ("medium (full)",       _MEDIUM_RESUME),
        ("long (full)",         _LONG_RESUME),
    ]

    results = {}
    for label, text in cases:
        doc = _make_doc(text, f"bench_{label}")
        _, durs = _time_it(
            lambda d=doc: extractor.extract(d.text, d.filename),
            runs=runs,
        )
        results[label] = {
            "char_count": len(text),
            "runs": runs,
            "mean_s": round(mean(durs), 2),
            "min_s": round(min(durs), 2),
            "max_s": round(max(durs), 2),
        }
        print(f"    {label:25s}  {len(text):6d} chars  {mean(durs):5.1f}s avg")

    return results


def bench_full_pipeline(parser: ResumeParser, runs: int = 1) -> dict:
    """Benchmark end-to-end: doc → parser → validate."""
    cases = [
        ("short",  _SHORT_RESUME),
        ("medium", _MEDIUM_RESUME),
        ("long",   _LONG_RESUME),
    ]

    results = {}
    for label, text in cases:
        doc = _make_doc(text, f"bench_{label}")

        def _run(d=doc):
            rec = parser.parse(d)
            return validate_candidate(rec)

        _, durs = _time_it(_run, runs=runs)
        results[label] = {
            "char_count": len(text),
            "runs": runs,
            "mean_s": round(mean(durs), 2),
            "min_s": round(min(durs), 2),
            "max_s": round(max(durs), 2),
        }
        print(f"    {label:25s}  {len(text):6d} chars  {mean(durs):5.1f}s avg")

    return results


def bench_batch(parser: ResumeParser) -> dict:
    """Benchmark sequential processing of a 5-resume batch."""
    texts = [_SHORT_RESUME, _MEDIUM_RESUME, _SHORT_RESUME, _MEDIUM_RESUME, _LONG_RESUME]
    t0 = time.monotonic()
    for i, text in enumerate(texts):
        doc = _make_doc(text, f"batch_{i}.txt")
        rec = parser.parse(doc)
        validate_candidate(rec)
    total = time.monotonic() - t0
    return {
        "batch_size": len(texts),
        "total_s": round(total, 2),
        "per_resume_avg_s": round(total / len(texts), 2),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark AI extraction pipeline.")
    ap.add_argument("--short-only", action="store_true", help="Only benchmark short resume.")
    ap.add_argument("--runs", type=int, default=1, help="Inference repeats per case.")
    ap.add_argument("--rules-only", action="store_true", help="Skip AI, measure rules only.")
    ap.add_argument("--output-dir", default="bench_results/", help="Directory for result JSON.")
    args = ap.parse_args()

    print(f"\n{'='*60}")
    print("  Resume-to-Excel — Performance Benchmark")
    print(f"{'='*60}")

    # ---- Reader ----------------------------------------------------------
    print("\n1. Document reader (text extraction from files on disk):")
    reader_results = bench_reader(runs=max(1, args.runs))
    for fname, data in reader_results.items():
        if isinstance(data, dict) and "mean_s" in data:
            print(f"    {fname:30s}  {data['mean_s']:.3f}s avg  ({data['size_kb']} KB)")
        else:
            print(f"    {data}")

    # ---- AI inference ----------------------------------------------------
    extractor = None
    if not args.rules_only:
        running, msg = check_ollama_running()
        if not running:
            print(f"\n⚠️  Ollama not running ({msg}). Skipping AI benchmarks.")
            args.rules_only = True
        else:
            ok, _ = check_model_available("qwen3:4b")
            if ok:
                extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0, think=False))
            else:
                print("⚠️  qwen3:4b not available. Skipping AI benchmarks.")
                args.rules_only = True

    inference_results = {}
    if not args.rules_only and extractor:
        print("\n2. AI inference (Ollama / qwen3:4b):")
        inference_results = bench_inference(extractor, runs=args.runs)

    # ---- Full pipeline ---------------------------------------------------
    parser = ResumeParser(ai_extractor=extractor)
    print("\n3. Full pipeline (text → parse → validate):")
    pipeline_results = bench_full_pipeline(parser, runs=args.runs)

    # ---- Batch -----------------------------------------------------------
    print("\n4. Batch processing (5 mixed resumes, sequential):")
    batch_results = bench_batch(parser)
    print(f"    {batch_results['batch_size']} resumes  "
          f"{batch_results['total_s']:.1f}s total  "
          f"{batch_results['per_resume_avg_s']:.1f}s/resume avg")

    # ---- Summary ---------------------------------------------------------
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    if pipeline_results:
        for label, d in pipeline_results.items():
            print(f"  {label:10s}: {d['mean_s']:.1f}s avg")
    print(f"  Batch avg per resume: {batch_results['per_resume_avg_s']:.1f}s")

    # ---- Save ------------------------------------------------------------
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = output_dir / f"bench_{ts}.json"
    payload = {
        "benchmarked_at": datetime.now().isoformat(),
        "mode": "rules_only" if args.rules_only else "ai",
        "reader": reader_results,
        "inference": inference_results,
        "pipeline": pipeline_results,
        "batch": batch_results,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n  💾 Results saved: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
