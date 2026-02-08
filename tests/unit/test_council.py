from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.council.council import (
    CouncilAction,
    CouncilDecision,
    GrandCouncil,
    ModuleVote,
    SignalStrength,
)
from argus_py.council.weights import CouncilWeights
from argus_py.models.aether.aether import AetherComponents, AetherResult, MacroRegime
from argus_py.models.hermes.hermes import HermesResult, Sentiment
from argus_py.council.defs import Vote


def _aether(score=65.0):
    return AetherResult(
        regime=MacroRegime.RISK_ON,
        score=score,
        components=AetherComponents(
            fear_greed=40,
            btc_dominance=45,
            total_mcap_change=2.0,
            dxy_trend="DOWN",
            funding_rate=-0.0005,
        ),
        reasoning="macro",
    )


def _hermes(sentiment_score=20.0):
    return HermesResult(
        overall_sentiment=Sentiment.POSITIVE,
        sentiment_score=sentiment_score,
        articles_analyzed=5,
        top_headlines=["x"],
        reasoning="news",
    )


def test_regime_weight_selection():
    assert CouncilWeights.get_for_regime("TREND") == CouncilWeights.TREND_WEIGHTS
    assert CouncilWeights.get_for_regime("CHOP") == CouncilWeights.CHOP_WEIGHTS
    assert CouncilWeights.get_for_regime("RISK_OFF") == CouncilWeights.RISK_OFF_WEIGHTS


def test_weighted_score_calculation_correct():
    council = GrandCouncil()
    votes = [
        ModuleVote("orion", 80, "LONG", 0.8, []),
        ModuleVote("aether", 60, "LONG", 0.7, []),
    ]
    weights = {"orion": 0.5, "aether": 0.5}
    score = council._calculate_weighted_score(votes, weights)
    assert score == 70.0


def test_collect_votes_from_all_modules():
    council = GrandCouncil()
    votes = council._collect_votes(
        orion_vote=Vote("Orion", "LONG", 0.8, 75.0, ["t"]),
        aether_result=_aether(62),
        hermes_result=_hermes(10),
        phoenix_score=65.0,
        aegean_vote=ModuleVote("aegean", 70.0, "LONG", 0.7, ["m"]),
    )

    modules = {v.module for v in votes}
    assert modules == {"orion", "aether", "hermes", "phoenix", "aegean"}


def test_veto_logic_blocks_inappropriate_buys():
    council = GrandCouncil()
    votes = [
        ModuleVote("aether", 25, "SHORT", 0.9, []),
        ModuleVote("orion", 80, "LONG", 0.8, []),
        ModuleVote("hermes", 60, "LONG", 0.7, []),
    ]
    strength = council._check_vetoes(votes, CouncilAction.AGGRESSIVE_BUY)
    assert strength == SignalStrength.VETOED


def test_convene_returns_schema_and_types():
    council = GrandCouncil()
    decision = council.convene(
        orion_vote=ModuleVote("orion", 75, "LONG", 0.8, ["Trend up"]),
        aether_result=_aether(58),
        hermes_result=_hermes(20),
        phoenix_score=65,
        aegean_vote=ModuleVote("aegean", 70, "LONG", 0.7, ["Momentum"]),
        regime="TREND",
    )

    assert isinstance(decision, CouncilDecision)
    assert isinstance(decision.action, CouncilAction)
    assert isinstance(decision.strength, SignalStrength)
    assert isinstance(decision.confidence, float)
    assert isinstance(decision.reasoning, str)
    assert isinstance(decision.votes, list)
    assert isinstance(decision.weights_used, dict)


def test_convene_with_veto_downgrades_to_hold():
    council = GrandCouncil()
    decision = council.convene(
        orion_vote=ModuleVote("orion", 85, "LONG", 0.9, ["strong"]),
        aether_result=_aether(20),
        hermes_result=_hermes(40),
        phoenix_score=80,
        aegean_vote=ModuleVote("aegean", 78, "LONG", 0.8, ["momentum"]),
        regime="TREND",
    )

    assert decision.strength == SignalStrength.VETOED
    assert decision.action == CouncilAction.HOLD


def test_convene_example_from_contract_runs():
    council = GrandCouncil()
    decision = council.convene(
        orion_vote=ModuleVote("orion", 75, "LONG", 0.8, ["Trend up"]),
        aether_result=None,
        hermes_result=None,
        phoenix_score=65,
        aegean_vote=ModuleVote("aegean", 70, "LONG", 0.7, ["Momentum"]),
        regime="TREND",
    )

    assert decision.action in {
        CouncilAction.AGGRESSIVE_BUY,
        CouncilAction.ACCUMULATE,
        CouncilAction.HOLD,
        CouncilAction.TRIM,
        CouncilAction.LIQUIDATE,
    }
    assert decision.strength in {SignalStrength.STRONG, SignalStrength.NORMAL, SignalStrength.WEAK, SignalStrength.VETOED}
