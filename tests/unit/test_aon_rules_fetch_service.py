from backend.services.aon_rules_fetch_service import AonRulesFetchService


INDEX_HTML = """
<div class="main" id="main">
  <h1>Rules Index</h1>
  <a href="/Rules.aspx?ID=1">Introduction</a>
  <a href="/Rules.aspx?ID=97">Law and Chaos</a>
  <a href="/Rules.aspx?ID=97">Law and Chaos</a>
</div>
<div class="clear"></div>
"""


RULE_HTML = """
<div class="main" id="main">
<h1 style="text-align:center" class="hide-on-print"><a href="Rules.aspx"><u>Rules Index</u></a></h1>
<div class="rule-ancestors hide-on-print">
    <span class="rule-ancestor">Core Rulebook</span>
    <span class="rule-ancestor"><a href="/Rules.aspx?ID=1" class="link">Chapter 1: Introduction</a></span>
    <span class="rule-ancestor"><a href="/Rules.aspx?ID=95" class="link">Alignment</a></span>
</div>
<div class="sibling-navigation hide-on-print"></div>
<div class="rule">
    <h1 class="title">
        <a href="/Rules.aspx?ID=97">Law and Chaos</a>
    </h1>
    <div class="sources"><strong>Source</strong> <a href="/Sources.aspx?ID=1">Core Rulebook pg. 29</a></div>
    <div>
        Your character has a lawful alignment if they value consistency.<br /><br />
        Chaotic characters value spontaneity.
    </div>
</div>
<div class="sibling-navigation hide-on-print"></div>
</div>
<div class="clear"></div>
"""


def test_discover_rule_links_deduplicates_and_sorts():
    service = AonRulesFetchService()

    links = service.discover_rule_links(INDEX_HTML)

    assert [link.rule_id for link in links] == [1, 97]
    assert links[1].title == "Law and Chaos"
    assert links[1].url == "https://2e.aonprd.com/Rules.aspx?ID=97"


def test_parse_rule_page_extracts_title_ancestors_source_and_body():
    service = AonRulesFetchService()

    document = service.parse_rule_page(
        RULE_HTML,
        source_url="https://2e.aonprd.com/Rules.aspx?ID=97",
        rule_id=97,
        fallback_title="Fallback",
    )

    assert document.title == "Law and Chaos"
    assert document.ancestors == [
        "Core Rulebook",
        "Chapter 1: Introduction",
        "Alignment",
    ]
    assert document.source_citation == "Core Rulebook pg. 29"
    assert "Your character has a lawful alignment" in document.content
    assert "Chaotic characters value spontaneity." in document.content
    assert document.summary.startswith("Your character has a lawful alignment")
