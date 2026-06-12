"""
End-to-end demo script.
Run: python scripts/run_demo.py
Tests the full pipeline with a realistic Maharashtra GR sample.
"""
import asyncio
import json
from src.core.logging import setup_logging
from src.orchestrator.praison import PraisonOrchestrator

SAMPLE_GR = """
Government of Maharashtra
Department of Rural Development & Water Conservation

No. GR/RD/2024/CR-45/NR-1                      Date: 10 January 2024

GOVERNMENT RESOLUTION

Subject: Implementation of Jal Jeevan Mission - Phase II in all Gram Panchayats

Reference: Government of India, Ministry of Jal Shakti letter No. JJM/2023/Phase2/001
           dated 1 December 2023.

The Government of Maharashtra, having considered the directives of the Government 
of India under Jal Jeevan Mission Phase II, hereby resolves as follows:

1. All District Collectors shall ensure 100% household tap water connections in 
   their respective districts by 31 March 2025.

2. Chief Executive Officers of Zilla Parishads are directed to prepare district-wise 
   action plans within 30 days of issuance of this GR.

3. Gram Panchayats with populations exceeding 5,000 must establish Water Quality 
   Testing Laboratories by 30 June 2024.

4. Non-compliance will attract action under Maharashtra Gram Panchayat Act, 1958, 
   Section 56.

5. Funds to the tune of Rs. 2,500 Crores have been allocated for this purpose under 
   Budget Head 2215-A-01.

By order and in the name of the Governor of Maharashtra,

                                        Smt. Priya Kulkarni, IAS
                                        Principal Secretary
                                        Rural Development Department
"""

OFFICER_REQUEST = """
I am the District Collector of Pune. Please analyze this GR, identify my specific 
obligations and deadlines, and draft an official response to the Zilla Parishad CEO 
directing them to prepare the action plan.
"""


async def main():
    setup_logging("INFO")
    print("\n" + "="*60)
    print("  GOVERNMENT AI MULTI-AGENT ASSISTANT — DEMO")
    print("="*60 + "\n")

    orchestrator = PraisonOrchestrator()

    print("📋 Processing GR with full multi-agent pipeline...\n")
    result = await orchestrator.process(
        user_request=OFFICER_REQUEST,
        document_text=SAMPLE_GR,
    )

    print("✅ PIPELINE COMPLETE\n")
    print(f"📊 Confidence Score:     {result.confidence_score:.1%}")
    print(f"🔄 Negotiation Rounds:   {result.negotiation_rounds}")
    print(f"⏱  Processing Time:      {result.processing_time_ms:.0f}ms")
    print(f"🤖 Models Used:          {', '.join(result.models_used)}")
    print(f"📝 Compliance Verdict:   {result.compliance_report.verdict.value.upper()}")
    print(f"🎯 Compliance Score:     {result.compliance_report.overall_score:.1f}/100")

    print("\n" + "-"*60)
    print("EXTRACTED OBLIGATIONS:")
    for i, ob in enumerate(result.gr_analysis.key_obligations, 1):
        print(f"  {i}. {ob}")

    print("\nDEADLINES FOUND:")
    for d in result.gr_analysis.deadlines:
        print(f"  • {d}")

    if result.gr_analysis.ambiguities_detected:
        print("\n⚠️  AMBIGUITIES DETECTED:")
        for a in result.gr_analysis.ambiguities_detected:
            print(f"  ! {a}")

    print("\n" + "-"*60)
    print("HERMES COUNTER-ARGUMENTS:")
    for ca in result.compliance_report.counter_arguments:
        print(f"  ↔ {ca}")

    print("\n" + "-"*60)
    print("OFFICIAL DRAFT (excerpt):")
    print(result.human_readable_draft[:800] + "...")

    print("\n" + "-"*60)
    print("REASONING STEPS:")
    for step in result.reasoning_steps:
        print(f"  → {step}")

    # Save full output
    output_path = "demo_output.json"
    with open(output_path, "w") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, default=str)
    print(f"\n💾 Full JSON output saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())