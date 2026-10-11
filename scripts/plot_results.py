#!/usr/bin/env python3
"""Create dependency-free SVG charts from Shikai benchmark CSV files."""
import argparse, csv, statistics
from pathlib import Path

COLORS = ["#f97316", "#2563eb", "#16a34a", "#9333ea"]

def rows(path):
    with path.open(newline="", encoding="utf-8") as stream: return list(csv.DictReader(stream))

def svg_bar(path, title, labels, values, unit):
    width, height, left, top, bottom = 760, 430, 90, 60, 70
    plot_h, plot_w, maximum = height-top-bottom, width-left-30, max(values) * 1.15
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2}" y="32" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="bold">{title}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#334155"/>',
        f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#334155"/>']
    slot, bar_w = plot_w/len(values), min(110, plot_w/len(values)*0.55)
    for i, (label, value) in enumerate(zip(labels, values)):
        x, bar_h = left + slot*i + (slot-bar_w)/2, value/maximum*plot_h
        y = top + plot_h - bar_h
        parts += [f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" fill="{COLORS[i%len(COLORS)]}"/>',
            f'<text x="{x+bar_w/2:.1f}" y="{y-8:.1f}" text-anchor="middle" font-family="sans-serif" font-size="13">{value:.2f} {unit}</text>',
            f'<text x="{x+bar_w/2:.1f}" y="{top+plot_h+28}" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold">{label}</text>']
    parts.append('</svg>'); path.write_text("\n".join(parts), encoding="utf-8")

def svg_line(path, title, points, x_label, y_label):
    width, height, left, top, bottom = 780, 440, 90, 60, 75
    plot_h, plot_w = height-top-bottom, width-left-35
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    xmax, ymax = max(xs)*1.05, max(ys)*1.12
    coords = [(left+x/xmax*plot_w, top+plot_h-y/ymax*plot_h) for x,y in points]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="32" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="bold">{title}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#334155"/>', f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#334155"/>',
        f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in coords)}" fill="none" stroke="#f97316" stroke-width="3"/>']
    for (raw_x, raw_y), (x,y) in zip(points, coords):
        parts += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#f97316"/>', f'<text x="{x:.1f}" y="{y-12:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12">{raw_y:.0f}</text>', f'<text x="{x:.1f}" y="{top+plot_h+25}" text-anchor="middle" font-family="sans-serif" font-size="12">{raw_x:.0f}</text>']
    parts += [f'<text x="{left+plot_w/2}" y="{height-15}" text-anchor="middle" font-family="sans-serif" font-size="14">{x_label}</text>', f'<text x="18" y="{top+plot_h/2}" transform="rotate(-90 18 {top+plot_h/2})" text-anchor="middle" font-family="sans-serif" font-size="14">{y_label}</text>', '</svg>']
    path.write_text("\n".join(parts), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, nargs="+",
                        help="One or more all-results.csv files to combine")
    parser.add_argument("--quality-results", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/assets"))
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    data = [row for path in args.results for row in rows(path)]
    perf = [r for r in data if r.get("suite") == "performance"]
    labels = [p for p in ("int4", "int8", "fp16") if any(r.get("precision") == p for r in perf)]
    means = [statistics.fmean(float(r["throughput_tok_s"]) for r in perf if r["precision"] == p) for p in labels]
    if means:
        svg_bar(args.output/"precision-throughput.svg", "Decode throughput by weight precision", [p.upper() for p in labels], means, "tok/s")
    context = sorted(((float(r["input_tokens"]), float(r["ttft_ms"])) for r in data if r.get("suite") == "context"))
    if context:
        grouped = sorted({x for x, _ in context})
        context = [(x, statistics.fmean(y for raw_x, y in context if raw_x == x)) for x in grouped]
        svg_line(args.output/"context-ttft.svg", "Prompt length versus time to first token", context, "Formatted input tokens", "TTFT (ms)")
    quality_data = rows(args.quality_results) if args.quality_results else data
    quality = [r for r in quality_data if r.get("suite") == "quality"]
    qlabels = [p for p in ("int4", "int8", "fp16") if any(r.get("precision") == p for r in quality)]
    scores = [statistics.fmean(float(r["quality_score"]) for r in quality if r["precision"] == p) for p in qlabels]
    if scores:
        svg_bar(args.output/"quality-scores.svg", "Automatic quality rubric by precision", [p.upper() for p in qlabels], scores, "/2")

if __name__ == "__main__": main()
