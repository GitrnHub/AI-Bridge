"""Offline HTML/Markdown/CSV reports. No remote scripts, invented scores, or GPUs."""
from __future__ import annotations
import csv
import html
import json
from pathlib import Path


def _at(obj,*keys):
    for key in keys:
        if not isinstance(obj,dict):return None
        obj=obj.get(key)
    return obj


def summary_row(r:dict)->dict:
    return {"backend":r["backend"],"width":r["width"],"height":r["height"],
        "device":r.get("device"),"status":r["status"],
        "gt_pairs":_at(r,"accuracy","labeled_observable_pairs"),
        "coverage":_at(r,"accuracy","coverage"),
        "success_05px":_at(r,"accuracy","success_le_0.5px"),
        "success_1px":_at(r,"accuracy","success_le_1px"),
        "success_2px":_at(r,"accuracy","success_le_2px"),
        "error_mean_px_valid_only":_at(r,"accuracy","error_px_valid_only","mean"),
        "error_p95_px_valid_only":_at(r,"accuracy","error_px_valid_only","p95"),
        "resident_mean_ms":_at(r,"resident","wall_ms","mean"),
        "resident_p95_ms":_at(r,"resident","wall_ms","p95"),
        "resident_latency_fps":_at(r,"resident","fps_reciprocal_mean_latency"),
        "host_mean_ms":_at(r,"host_to_offset","wall_ms","mean"),
        "host_p95_ms":_at(r,"host_to_offset","wall_ms","p95"),
        "throughput_fps":_at(r,"throughput","fps"),
        "cpu_pct_one_core_100":_at(r,"telemetry","process_cpu_pct_one_core_100"),
        "rss_peak_mib":_at(r,"telemetry","fields","process_rss_mib","max"),
        "board_gpu_busy_pct":_at(r,"telemetry","fields","board_gpu_busy_pct","mean"),
        "board_dram_busy_pct":_at(r,"telemetry","fields","board_dram_busy_pct","mean"),
        "board_power_mean_w":_at(r,"telemetry","fields","board_power_w","mean"),
        "process_vram_peak_sampled_mib":_at(r,"telemetry","fields","process_gpu_memory_mib","max"),
        "torch_allocated_peak_mib":_at(r,"torch_memory_peak_mib","allocated"),
        "board_j_per_pair_estimate":_at(r,"energy_estimates","board_j_per_pair"),
        "false_accept_flat":_at(r,"accuracy","false_accept_rate_unobservable"),
        "load_p95_response_ms":_at(r,"load","response_ms","p95"),
        "load_deadline_misses":_at(r,"load","deadline_misses"),"error":r.get("error")}


def build_report(root:Path,results:list[dict])->None:
    rows=[summary_row(r) for r in results]
    with (root/"summary.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ["backend","status"])
        writer.writeheader();writer.writerows(rows)
    predictions=[]
    for r in results:
        for p in r.get("predictions",[]):
            predictions.append({"backend":r["backend"],"width":r["width"],"height":r["height"],**p})
    if predictions:
        with (root/"predictions.csv").open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
    columns=["backend","width","height","status","success_1px","error_mean_px_valid_only",
             "resident_mean_ms","resident_p95_ms","host_mean_ms","throughput_fps","board_power_mean_w"]
    def fmt(v):
        if v is None:return "N/A"
        if isinstance(v,float):return f"{v:.4g}"
        return str(v).replace("|","/").replace("\n"," ")
    notes=("Accuracy is a per-pair translation success rate (0..1), NOT dense optical-flow pixel accuracy. "
           "Invalid predictions count as failures; error means cover valid labeled pairs only. "
           "Unlabeled real pairs have no accuracy score. CPU runs are correctness smoke tests, never GPU results. "
           "CUDA elapsed time spans the dependency graph, not pure OFA/SM execution. "
           "NVML metrics describe the board, not OFA occupancy. Missing telemetry is N/A, not zero.")
    md=["# OFA comparison report","",notes,"","|"+"|".join(columns)+"|","|"+"|".join(["---"]*len(columns))+"|"]
    md.extend("|"+"|".join(fmt(row.get(c)) for c in columns)+"|" for row in rows)
    md.extend(["","## Evidence","","Each backend_resolution/result.json contains environment, exact parameters, per-scene accuracy, per-pair hashes, timings, failures and telemetry definitions.",
               "Board resource sampling covers the sustained resident run; host-transfer latency is measured separately. The historical OFA.zip log is not included as a new measurement."])
    (root/"report.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    head="""<!doctype html><meta charset="utf-8"><title>OFA GPU displacement comparison</title>
<style>body{font-family:system-ui;margin:2rem;background:#f6f8fa;color:#182230}h1{font-size:1.65rem}p{max-width:95rem;line-height:1.6}table{border-collapse:collapse;background:white;font-variant-numeric:tabular-nums}th,td{padding:.6rem .8rem;border-bottom:1px solid #dde3ea;text-align:right}th{background:#e8eef5;cursor:pointer;position:sticky;top:0}td:first-child,td:nth-child(4){text-align:left}.wrap{overflow:auto}a{color:#1652ad}</style>
<h1>GPU image-displacement comparison</h1><p>"""
    table="<div class=wrap><table id=results><thead><tr>"+"".join("<th>"+html.escape(c)+"</th>" for c in columns)+"</tr></thead><tbody>"
    for row in rows:
        table+="<tr>"+"".join("<td>"+html.escape(fmt(row.get(c)))+"</td>" for c in columns)+"</tr>"
    table+="</tbody></table></div>"
    links="<h2>Raw evidence</h2>"+"".join(f'<p><a href="{r["backend"]}_{r["width"]}x{r["height"]}/result.json">{html.escape(r["backend"])} {r["width"]}x{r["height"]}</a>: {html.escape(r.get("error",r["status"]))}</p>' for r in results)
    script="""<script>document.querySelectorAll('th').forEach((th,i)=>th.onclick=()=>{const b=document.querySelector('tbody');const r=[...b.rows];th.dataset.desc=th.dataset.desc==='1'?'0':'1';const sign=th.dataset.desc==='1'?-1:1;r.sort((a,b)=>{const x=a.cells[i].textContent,y=b.cells[i].textContent;return sign*(Number.isFinite(+x)&&Number.isFinite(+y)?+x-+y:x.localeCompare(y))});r.forEach(x=>b.appendChild(x))});</script>"""
    (root/"report.html").write_text(head+html.escape(notes)+"</p>"+table+links+script,encoding="utf-8")
