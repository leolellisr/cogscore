import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from agent_names import ALIASES, display_agent, relabel_figure

@pytest.mark.parametrize("alias,expected", sorted(ALIASES.items()))
def test_aliases(alias, expected):
    assert display_agent(alias) == expected

def test_no_partial_replacement():
    assert display_agent("Substage1_QL_Noise") == "CS6_nEC"
    assert display_agent("Substage1_Theoretic") == "CS1_T"
    assert display_agent("Substage3_Theoretic") == "CS3_T"
    assert display_agent("Substage10") == "Substage10"
    assert display_agent("mean_reward") == "mean_reward"

def test_relabel_does_not_change_plot_data():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    line, = ax.plot([1, 2], [4.0, 7.0], label="Substage1_DQN")
    ax.legend()
    before = (line.get_xdata().copy(), line.get_ydata().copy())
    relabel_figure(fig)
    assert ax.get_legend().get_texts()[0].get_text() == "CS1"
    assert list(line.get_xdata()) == list(before[0])
    assert list(line.get_ydata()) == list(before[1])
    plt.close(fig)


def test_theoretic_plot_labels_keep_numerical_series():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    a, = ax.plot([1, 2, 3], [0.1, 0.4, 0.2], label="Substage1_Theoretic")
    b, = ax.plot([1, 2, 3], [0.3, 0.2, 0.6], label="Substage3_Theoretic")
    old = [(tuple(x.get_xdata()), tuple(x.get_ydata())) for x in (a, b)]
    ax.legend()
    relabel_figure(fig)
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["CS1_T", "CS3_T"]
    assert old == [(tuple(x.get_xdata()), tuple(x.get_ydata())) for x in (a, b)]
    plt.close(fig)
