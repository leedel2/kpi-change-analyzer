from jinja2 import Environment, FileSystemLoader
import json

env = Environment(loader=FileSystemLoader("app/templates"))

def generate_markdown_report(data, use_ai=False):
    template = env.get_template("report.md.jinja")

    summary = (
        f"{data['meta']['metric_analyzed']} changed "
        f"{data['period_comparison']['relative_change_pct']}% "
        f"({data['period_comparison']['direction']})."
    )

    return template.render(
        summary=summary,
        data=json.dumps(data, indent=2)
    )

