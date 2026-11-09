#!/usr/bin/env python3
"""Append current validation and KV findings to the historical academic PDF.

Requires requirements/report.lock.txt. Repeated runs replace the appendix rather
than duplicating it. The original academic pages and measurements are preserved.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import shutil
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

PROJECT = Path(__file__).resolve().parents[1]


def read_rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=PROJECT / 'output/pdf/PRABHAT-JHA_SWFW_5S_13.pdf')
    parser.add_argument('--evidence', type=Path, default=PROJECT / 'results/validated-20261103')
    args = parser.parse_args()
    verification = json.loads((args.evidence / 'verification/summary.json').read_text())
    rows = read_rows(args.evidence / 'conversation/all-results.csv')
    quality = read_rows(args.evidence / 'quality/all-results.csv')
    original = PdfReader(io.BytesIO(args.report.read_bytes()))
    if (original.metadata or {}).get('/ShikaiIntegratedReport') == 'true':
        parser.error('This report already integrates current validation, the linked index and requirements review. '
                     'Rebuild it with docs/submission/build_academic_report.py in the local report environment; '
                     'the legacy appendix updater would discard its navigation.')
    base_pages = int((original.metadata or {}).get('/ShikaiBasePages', len(original.pages)))
    font_dir = PROJECT / '.cache/submission-fonts'
    normal, bold = 'Times-Roman', 'Times-Bold'
    if (font_dir / 'Times.TTF').exists() and (font_dir / 'Timesbd.TTF').exists():
        pdfmetrics.registerFont(TTFont('ReportTimes', str(font_dir / 'Times.TTF')))
        pdfmetrics.registerFont(TTFont('ReportTimesBold', str(font_dir / 'Timesbd.TTF')))
        normal, bold = 'ReportTimes', 'ReportTimesBold'
    body = ParagraphStyle('Body', fontName=normal, fontSize=11, leading=14.5,
        alignment=TA_JUSTIFY, spaceAfter=8)
    heading = ParagraphStyle('Heading', fontName=bold, fontSize=14, leading=18, spaceAfter=12)
    cell = ParagraphStyle('Cell', fontName=normal, fontSize=9.3, leading=12)
    story = []

    def para(text):
        story.append(Paragraph(escape(text), body))

    def table(headers, data, widths):
        cells = [[Paragraph(escape(str(value)), cell) for value in row] for row in [headers, *data]]
        view = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        view.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LINEBELOW', (0, 0), (-1, 0), .6, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), .6, colors.black)]))
        story.extend([view, Spacer(1, 12)])

    def avg(group, key):
        values = [float(row[key]) for row in group if row.get(key) not in ('', None)]
        return sum(values) / len(values)

    story.append(Paragraph('Validation and KV-cache addendum - 3 November 2026', heading))
    para('This addendum supersedes the earlier report\'s current-status statements. The original October measurements, screenshots and limitations remain historical evidence. New measurements use the same i5-13420H laptop and pinned OpenVINO runtime; power, thermals and background load were not laboratory controlled.')
    para(f"Current release build: passed. CTest: {verification['ctest_passed']} passed, "
        f"{verification['ctest_failed']} failed, {verification['ctest_skipped']} skipped. "
        f"The preparation/reporting suite contains {verification['script_tests']} passing regressions. "
        'A fresh three-turn conversation passed under an inherited Linux seccomp filter that denied all non-AF_UNIX socket creation, including TCP/UDP sockets. This verifies enforced network denial without claiming that a network namespace was created.')
    para('Implemented since the original report: streamed and cancellable single-prompt generation; fixed KV block pools; U4 cache requests; configurable prefill chunking and eviction areas; coherent conversation benchmarks; direct cache-allocation diagnostics; cache release/reload on reset for prefix-enabled sessions; and a verified packager that includes current uncommitted source, CI and guides.')
    story.append(Paragraph('Conversation latency study', heading))
    para('Seven CPU/INT4 profiles, three fresh-process conversations per profile, three turns per conversation, four inference threads and up to 16 output tokens. The first prompt has 538 formatted input tokens. Cold-turn latency and subsequent-turn latency are reported separately.')
    data = []
    for profile in ('baseline', 'prefix-128', 'prefix-256-chunk64', 'prefix-128-u8', 'prefix-128-u4', 'eviction-256', 'eviction-1024'):
        group = [row for row in rows if row.get('profile') == profile and row.get('status') == 'ok']
        cold = [row for row in group if row['id'] == 'turn-1']
        warm = [row for row in group if row['id'] != 'turn-1']
        data.append([profile, f"{avg(cold, 'ttft_ms'):.0f}", f"{avg(warm, 'ttft_ms'):.0f}", f"{avg(group, 'peak_rss_mib'):.1f}"])
    table(['Profile', 'Cold TTFT ms', 'Follow-up ms', 'Peak RSS MiB'], data, [170, 92, 92, 108])
    para('The 128-block automatic prefix profile reduced follow-up TTFT from 3821.68 ms to 236.79 ms (about 16.1x) in this workload. Cold TTFT stayed near 6.1 seconds. All profiles failed exact code recall, and generated answers differed. Prefix reuse is therefore an opt-in speed profile; answer equivalence is not claimed. Eviction did not show a useful improvement here.')
    story.append(PageBreak())
    story.append(Paragraph('Direct cache allocation and quality checks', heading))
    para('The cache-probe command uses ContinuousBatchingPipeline with the application\'s scheduler/device-property builders. Its native allocated-byte counter includes free pool blocks. This is a separate diagnostic pipeline, not an estimate derived from RSS or an allocation reading from LLMPipeline.')
    data = []
    for profile in ('auto-128', 'u4-128', 'f16-128', 'auto-1gb'):
        measured = read_rows(args.evidence / f'allocation/{profile}.csv')
        data.append([profile, f"{int(measured[0]['cache_allocated_bytes'])/1024**2:.2f}",
            f"{max(float(row['max_cache_usage_percent']) for row in measured):.4f}"])
    table(['Probe setting', 'Allocated cache MiB', 'Maximum usage %'], data, [190, 142, 130])
    para('Each probe repeats the same 35-input-token prompt three times with up to 8 output tokens. A 128-block automatic pool reserved 64.75 MiB versus 1023.86 MiB for the 1 GB pool, about 93.7% less reservation. U4 reserved 73.50 MiB, MORE than automatic precision for the same block count; requesting fewer bits did not establish a better layout. These are cache reservations, not total physical RAM savings.')
    baseline = {row['id']: row['response'] for row in quality if row.get('workload') == 'quality' and row['profile'] == 'baseline'}
    data = []
    for profile in ('baseline', 'prefix-128'):
        group = [row for row in quality if row.get('workload') == 'quality' and row['profile'] == profile]
        agree = sum(row['response'] == baseline.get(row['id']) for row in group)
        data.append([profile, len(group), f"{avg(group, 'quality_score'):.2f}", f'{agree}/{len(group)}'])
    table(['Independent quality profile', 'Cases', 'Rubric /2', 'Exact vs baseline'], data, [190, 55, 95, 122])
    para('The quality check uses one 128-token-limited greedy answer per each of five existing fixtures. The concept-matching rubric can reward incorrect or instruction-inconsistent answers; saved responses remain the evidence. Repeated greedy answers would not add independent accuracy samples.')
    para('Recommended usage: retain CPU/INT4 with automatic cache precision as the baseline. For repeated chat prefixes, try configs/cpu-prefix.json. Increasing context requires checking pool capacity. Smaller prefill chunks and eviction should be evaluated independently. Resetting a prefix-enabled session rebuilds the model pipeline to release retained cache ownership and includes reload time.')
    para('Remaining limits: the small model\'s long-context recall is unresolved; Intel GPU remains experimental; RTX 3050 compilation and NPU inference remain unvalidated paths; no full model re-export in a newly installed environment was repeated. These limitations are not represented as completed features.')
    para('Reproduction and evidence: guides/kv-cache.md; scripts/benchmark_kv.py; the cache-probe command; results/validated-20261103/. Primary references: OpenVINO continuous-batching and KV-cache-eviction guides, and the installed 2026.4.1 C++ headers. The source ZIP includes entry-level SHA-256 hashes and is tested after extraction.')

    buffer = io.BytesIO()
    def footer(canvas, doc):
        canvas.setFont(normal, 9)
        canvas.drawString(66, 806, 'Shikai - SWFW_5S_13 - November validation addendum')
        canvas.drawCentredString(297.6, 32, str(base_pages + doc.page))
    SimpleDocTemplate(buffer, pagesize=(595.276, 841.89), leftMargin=66, rightMargin=67,
        topMargin=60, bottomMargin=54).build(story, onFirstPage=footer, onLaterPages=footer)
    appendix = PdfReader(buffer)
    if len(appendix.pages) != 2:
        raise RuntimeError(f'Expected a two-page appendix, got {len(appendix.pages)}; inspect layout before updating the report')
    writer = PdfWriter()
    for page in original.pages[:base_pages]: writer.add_page(page)
    for page in appendix.pages: writer.add_page(page)
    writer.add_metadata({'/Title': 'Shikai: Local LLM inference - validated submission',
        '/Author': 'Prabhat Jha', '/ShikaiBasePages': str(base_pages)})
    backup = args.report.parent / 'previous-20261020' / args.report.name
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.report, backup)
    temporary = args.report.with_suffix('.pdf.tmp')
    with temporary.open('wb') as stream: writer.write(stream)
    temporary.replace(args.report)
    print(f'Updated report: {args.report}, {base_pages + len(appendix.pages)} pages')


if __name__ == '__main__':
    main()
