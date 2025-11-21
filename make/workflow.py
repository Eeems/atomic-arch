import json
import heapq

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any, cast


from . import IMAGE
from . import BUILDER

from .config import parse_all_config
from .config import Config

type Graph = dict[str, dict[str, str | list[str] | None | bool]]
type Indegree = dict[str, int]

kwds: dict[str, str] = {
    "help": "Regenerate the github workflow files",
}


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    config: Config = parse_all_config()

    def build_job_graph(config: Config) -> tuple[Graph, Indegree]:
        graph: Graph = {
            "rootfs": {
                "depends": "check",
                "cleanup": False,
            }
        }
        indegree: Indegree = {"rootfs": 0}
        for variant, data in cast(
            dict[str, dict[str, str | None | list[str]]], config["variants"]
        ).items():
            if variant in ("check", "rootfs"):
                raise ValueError(f"Invalid use of protected variant name: {variant}")

            graph[variant] = {
                "depends": data.get("depends", None) or "rootfs",
                "cleanup": False,
            }
            indegree[variant] = 0
            for template in cast(list[str], data["templates"]):
                full_id = f"{variant}-{template}"
                graph[full_id] = {
                    "depends": (
                        f"{variant}-{template.rsplit('-', 1)[0]}"
                        if "-" in template
                        else variant
                    ),
                    "cleanup": cast(bool, data.get("clean", False)),
                }
                indegree[full_id] = 0

        for job_id, data in graph.items():
            depends = data["depends"]
            if job_id == "rootfs":
                continue

            indegree[job_id] += 1
            if depends not in graph:
                raise RuntimeError(f"{job_id} cannot find dependency {depends}")

        return graph, indegree

    def topological_sort(graph: Graph, indegree: Indegree) -> list[str]:
        heap: list[str] = []
        for job, deg in indegree.items():
            if deg == 0:
                heapq.heappush(heap, job)

        order: list[str] = []
        while heap:
            job = heapq.heappop(heap)
            order.append(job)
            for dep_job, data in graph.items():
                if data["depends"] != job:
                    continue

                indegree[dep_job] -= 1
                if indegree[dep_job] == 0:
                    heapq.heappush(heap, dep_job)

        if len(order) != len(graph):
            raise RuntimeError("Cycle detected in job dependencies")

        return order

    graph, indegree = build_job_graph(config)

    def indent(lines: list[str], level: int = 1) -> list[str]:
        return [
            (("  " * level) + line).rstrip() if line.strip() else "" for line in lines
        ]

    def comment(title: str) -> list[str]:
        return [
            "  ######################################",
            f"  #             {title:<19}#",
            "  ######################################",
        ]

    def render_build(job_id: str) -> list[str]:
        d = graph[job_id]
        depends = d["depends"]
        lines = [
            f"{job_id}:",
            f"  name: Build {IMAGE}:{job_id} image",
            f"  needs: {depends}",
            "  uses: ./.github/workflows/build-variant.yaml",
            "  secrets: inherit",
            "  permissions: *permissions",
            "  with:",
            f"    variant: {job_id}",
            "    push: ${{ github.event_name != 'pull_request' }}",
        ]
        if job_id != "rootfs":
            lines += [
                f"    updates: ${{{{ fromJson(needs['{depends}'].outputs.updates) }}}}",
                f"    artifact: {depends}",
                f"    digest: ${{{{ needs['{depends}'].outputs.digest }}}}",
            ]

        if d["cleanup"]:
            lines.append("    cleanup: true")

        return indent(lines)

    def render_scan(job_id: str) -> list[str]:
        return indent(
            [
                f"scan_{job_id}:",
                f"  name: Scan image for {job_id}",
                f"  if: github.event_name != 'pull_request' || fromJson(needs['{job_id}'].outputs.updates)",
                f"  needs: {job_id}",
                "  uses: ./.github/workflows/scan.yaml",
                "  secrets: inherit",
                "  permissions: *permissions",
                "  with:",
                f"    variant: {job_id}",
                "    push: ${{ github.event_name != 'pull_request' }}",
                f"    artifact: ${{{{ fromJson(needs['{job_id}'].outputs.updates) && '{job_id}' || '' }}}}",
                f"    digest: ${{{{ needs['{job_id}'].outputs.digest }}}}",
            ]
        )

    def render_iso(job_id: str) -> list[str]:
        def __(offline: bool):
            return [
                f"{'offline' if offline else 'online'}_iso_{job_id}:",
                f"  name: Generate iso for {job_id}",
                f"  needs: {job_id}",
                "  uses: ./.github/workflows/iso.yaml",
                "  secrets: inherit",
                "  permissions: *permissions",
                "  with:",
                f"    variant: {job_id}",
                f"    artifact: {job_id}",
                f"    digest: ${{{{ needs['{job_id}'].outputs.digest }}}}",
                f"    pull: ${{{{ github.event_name != 'pull_request' && fromJson(needs['{job_id}'].outputs.updates) }}}}",
                f"    offline: {json.dumps(offline)}",
                "    push: ${{ github.event_name != 'pull_request' }}",
            ]

        return indent([*__(False), "", *__(True)])

    build_order = topological_sort(graph, indegree)

    sections = [
        [
            "#########################################",
            "# THIS FILE IS DYNAMICALLY GENERATED    #",
            "# Run the following to update the file: #",
            "#   $ ./make.py workflow                #",
            "#########################################",
            "name: Build images",
            "on:",
            "  pull_request: &on-filter",
            "    branches:",
            "      - master",
            "    paths:",
            "      - .github/workflows/build.yaml",
            "      - .github/workflows/build-variant.yaml",
            "      - .github/workflows/iso.yaml",
            "      - .github/workflows/manifest.yaml",
            '      - ".github/actions/**"',
            '      - "tools/dockerfile2llbjson/**"',
            '      - "make/__main__.py"',
            '      - "make/__init__.py"',
            '      - "make/iso.py"',
            '      - "make/scan.py"',
            '      - "make/build.py"',
            '      - "make/checkupdates.py"',
            '      - "make/manifest.py"',
            '      - "make/check.py"',
            '      - "make/workflow.py"',
            "      - make.py",
            "      - seccomp.json",
            "      - .containerignore",
            '      - "overlay/**"',
            '      - "templates/**"',
            '      - "variants/**"',
            "  push: *on-filter",
            "  workflow_dispatch:",
            "  schedule:",
            '    - cron: "0 23 * * *"',
            "",
            "concurrency:",
            "  group: build-${{ github.ref_name }}",
            "  cancel-in-progress: true",
            "",
            "jobs:",
        ],
        comment("UNIQUE"),
        indent(
            [
                "notifications:",
                "  name: Clear notifications",
                "  runs-on: ubuntu-latest",
                "  steps:",
                "    - name: Checkout the repository",
                "      uses: actions/checkout@v4",
                "    - name: Clean cancellation notifications",
                "      uses: ./.github/actions/clean-cancelled-notifications",
                "      with:",
                "        pat: ${{ secrets.NOTIFICATION_PAT }}",
                "",
                "wait:",
                "  name: Wait for builder to finish",
                "  runs-on: ubuntu-latest",
                "  permissions:",
                "    contents: read",
                "    actions: read",
                "  steps:",
                "    - name: Wait",
                "      uses: NathanFirmo/wait-for-other-action@8241e29ea2e9661a8af6d319b1d074825a299730",
                "      with:",
                "        token: ${{ github.token }}",
                "        workflow: 'tool-builder.yaml'",
                "",
                "check:",
                "  name: Ensure config is valid",
                "  runs-on: ubuntu-latest",
                "  needs: wait",
                "  permissions:",
                "    contents: read",
                "    packages: read",
                "  container:",
                f"    image: {BUILDER}:${{{{ github.head_ref || github.ref_name }}}}",
                "    options: >-",
                "      --privileged",
                "      --security-opt seccomp=unconfined",
                "      --security-opt apparmor=unconfined",
                "      --cap-add=SYS_ADMIN",
                "      --cap-add=NET_ADMIN",
                "      --device /dev/fuse",
                "      --tmpfs /tmp",
                "      --tmpfs /run",
                "      --userns=host",
                "      -v /:/run/host",
                "  steps:",
                "    - name: Checkout the repository",
                "      uses: actions/checkout@v4",
                "    - name: Cache venv",
                "      uses: actions/cache@v4",
                "      with:",
                "        path: .venv",
                "        key: venv-${{ hashFiles('.github/workflows/Dockerfile.builder') }}-${{ hashFiles('make.py') }}",
                "    - name: Cache go",
                "      uses: actions/cache@v4",
                "      with:",
                "        path: |",
                "          ~/go/pkg/mod",
                "          ~/.cache/go-build",
                "        key: go-${{ hashFiles('**/go.mod') }}-${{ hashFiles('**/go.sum') }}",
                "    - name: Ensure config is valid",
                "      shell: bash",
                "      run: |",
                "        set -e",
                "        ./make.py check",
                "        ./make.py workflow",
                '        git config --global --add safe.directory "$(realpath .)"',
                '        if [[ -n "$(git status -s)" ]]; then',
                '          echo "Please run ./make.py workflow, commit the changes, and try again."',
                "          git status -s",
                "          exit 1",
                "        fi",
                "      env:",
                "        TMPDIR: ${{ runner.temp }}",
                "",
                "manifest:",
                "  name: Generate manifest",
                '  if: "!cancelled()"',
                "  needs:",
                *[f"    - {j}" for j in sorted(build_order)],
                "  uses: ./.github/workflows/manifest.yaml",
                "  secrets: inherit",
                "  permissions: &permissions",
                "    contents: write",
                "    actions: write",
                "    packages: write",
                "    security-events: write",
                "  with:",
                "    cache: false",
            ]
        ),
        comment("BUILD"),
        *[render_build(j) for j in build_order],
        comment("SCAN"),
        *[render_scan(j) for j in build_order],
        comment("ISO"),
        *[render_iso(j) for j in build_order if j != "rootfs"],
    ]

    output: list[str] = []
    for i, sec in enumerate(sections):
        output.extend(sec)
        if i < len(sections) - 1:
            output.append("")

    with open(".github/workflows/build.yaml", "w") as f:
        _r = f.write("\n".join(output).rstrip() + "\n")


if __name__ == "__main__":
    kwds["description"] = kwds["help"]
    del kwds["help"]
    parser = ArgumentParser(
        **cast(  # pyright: ignore[reportAny]
            dict[str, Any],  # pyright: ignore[reportExplicitAny]
            kwds,
        ),
    )
    register(parser)
    args = parser.parse_args()
    command(args)
