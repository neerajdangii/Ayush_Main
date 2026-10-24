import re
from html import escape

VITAMIN_ANALYSIS_REPORT_NAME = "Vitamin Analysis Report"

GENERIC_RESULT_ROW_TEMPLATE = """
<tr>
  <td style="text-align:center;">{serial}</td>
  <td>{test_name}</td>
  <td style="text-align:center;">&nbsp;</td>
  <td style="text-align:center;">&nbsp;</td>
  <td style="text-align:center;">&nbsp;</td>
</tr>
""".strip()

GENERIC_RESULT_TABLE_TEMPLATE = """
<table style="width:100%;border-collapse:collapse;" border="1">
  <thead>
    <tr>
      <th style="width:8%;text-align:center;">S.No.</th>
      <th style="width:32%;text-align:center;">Test Parameters</th>
      <th style="width:25%;text-align:center;">Results/Observation</th>
      <th style="width:20%;text-align:center;">Specification/Limits</th>
      <th style="width:15%;text-align:center;">Method</th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
""".strip()

VITAMIN_ANALYSIS_REPORT_HTML = """
<p><em>{{non_nabl_section_started}}</em></p>
<table class="border doNotRemove">
  <thead>
    <tr class="greybg">
      <th>S.No.</th>
      <th colspan="3">Test Parameters</th>
      <th>Results/Observation</th>
      <th>Specification/Limits</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td colspan="3">Description</td>
      <td><span lang="EN-US">Clear colourless solution filled in flint glass sealed ampoule with yellow dot at constriction.</span></td>
      <td><span lang="EN-US">A clear colourless to pale yellow solution filled in flint glass sealed ampoule with yellow dot at constriction.</span></td>
    </tr>
    <tr>
      <td>3</td>
      <td colspan="3">
        <p><span lang="EN-US">Particulate Matter</span></p>
        <p><span lang="EN-US">Visible</span></p>
      </td>
      <td><span lang="EN-US">Complies</span></td>
      <td><span lang="EN-US">When a solution examined under suitable condition of visibility are clear and practically free from particle that can be observed as visual inspection by unaided eye.</span></td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>3.1</td>
      <td colspan="3">
        <p><span lang="EN-US">Sub-visible</span></p>
        <p><span lang="EN-US">(Avg. of 3 run)</span></p>
      </td>
      <td>
        <p class="MsoHeader"><span lang="EN-US">278/ Container</span></p>
        <p class="MsoHeader">7.3/Container&nbsp;</p>
      </td>
      <td>
        <p><span lang="EN-US">Max. particle limit &ge; 10&micro; = NMT 6000/ Container</span></p>
        <p><span lang="EN-US">Max. particle limit &ge; 25&micro;&nbsp;= NMT 600/ Container</span></p>
      </td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">
        <p><span lang="EN-US">Sub-visible</span></p>
        <p><span lang="EN-US">(Avg. of 3 run)</span></p>
      </td>
      <td>
        <p class="MsoHeader"><span lang="EN-US">278/ Container</span></p>
        <p class="MsoHeader">7.3/Container&nbsp;</p>
      </td>
      <td>
        <p><span lang="EN-US">Max. particle limit &ge; 10&micro; = NMT 6000/ Container</span></p>
        <p><span lang="EN-US">Max. particle limit &ge; 25&micro;&nbsp;= NMT 600/ Container</span></p>
      </td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>&nbsp;</td>
      <td>
        <p><span lang="EN-US">Max. particle limit &ge; 10&micro; = NMT 6000/ Container</span></p>
        <p><span lang="EN-US">Max. particle limit &ge; 25&micro;&nbsp;= NMT 600/ Container</span></p>
      </td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>
        <p><span lang="EN-US">Max. particle limit &ge; 10&micro; = NMT 6000/ Container</span></p>
        <p><span lang="EN-US">Max. particle limit &ge; 25&micro;&nbsp;= NMT 600/ Container</span></p>
      </td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>&nbsp;</td>
      <td colspan="3">&nbsp;</td>
      <td>
        <p><span lang="EN-US">Max. particle limit &ge; 10&micro; = NMT 6000/ Container</span></p>
        <p><span lang="EN-US">Max. particle limit &ge; 25&micro;&nbsp;= NMT 600/ Container</span></p>
      </td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <th>COMPOSITION</th>
      <th>RESULTS</th>
      <th>LABEL CLAIM</th>
      <th>%LABEL CLAIM</th>
      <th>LIMITS</th>
      <th>METHOD</th>
    </tr>
    <tr>
      <td><span lang="EN-US">Etophylline IP</span></td>
      <td><span lang="EN-US">169.6374&nbsp; mg</span></td>
      <td><span lang="EN-US">169.4 mg</span>&nbsp;</td>
      <td>100.14%&nbsp;</td>
      <td>90.0% to 110.0%</td>
      <td>M.S.</td>
    </tr>
  </tbody>
</table>
""".strip()


def build_generic_result_table(test_names):
    names = [str(name).strip() for name in (test_names or []) if str(name).strip()]
    if not names:
        names = ["Parameter Name"]

    rows = "\n".join(
        GENERIC_RESULT_ROW_TEMPLATE.format(serial=index, test_name=escape(name))
        for index, name in enumerate(names, start=1)
    )
    return GENERIC_RESULT_TABLE_TEMPLATE.format(rows=rows)


def build_tests_without_templates_table(tests):
    """Build a results table for tests that don't have custom templates."""
    if not tests:
        return ""
    
    rows = "\n".join(
        GENERIC_RESULT_ROW_TEMPLATE.format(serial=index, test_name=escape(test.name))
        for index, test in enumerate(tests, start=1)
    )
    return GENERIC_RESULT_TABLE_TEMPLATE.format(rows=rows)


COMPOSITION_MARKER_RE = re.compile(r"COMPOSITION", re.IGNORECASE)
TBODY_RE = re.compile(r"(<tbody[^>]*>)(.*?)(</tbody>)", re.IGNORECASE | re.DOTALL)
ROW_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)


def _build_template_main_row(serial, test_name):
    return (
        "<tr>"
        f'<td style="text-align: center;"><span style="font-family: helvetica, arial, sans-serif;">{serial}</span></td>'
        f"<td>{escape(test_name)}</td>"
        '<td colspan="2">&nbsp;</td>'
        '<td colspan="2">&nbsp;</td>'
        "</tr>"
    )


def populate_main_table_rows(template_html, test_names):
    names = [str(name).strip() for name in (test_names or []) if str(name).strip()]
    if not template_html or not names:
        return template_html

    tbody_match = TBODY_RE.search(template_html)
    if not tbody_match:
        return template_html

    tbody_inner = tbody_match.group(2)
    rows = ROW_RE.findall(tbody_inner)
    if not rows:
        return template_html

    composition_index = next(
        (index for index, row in enumerate(rows) if COMPOSITION_MARKER_RE.search(re.sub(r"<[^>]+>", " ", row))),
        None,
    )
    if composition_index is None:
        return template_html

    header_rows = rows[:1]
    composition_and_after = rows[composition_index:]
    dynamic_rows = [_build_template_main_row(index, name) for index, name in enumerate(names, start=1)]
    new_tbody = "\n".join(header_rows + dynamic_rows + composition_and_after)

    return (
        template_html[:tbody_match.start(2)]
        + new_tbody
        + template_html[tbody_match.end(2):]
    )
