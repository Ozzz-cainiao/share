from __future__ import annotations

import argparse
from pathlib import Path

from asset_catalog import ASSETS
from investlab.data import UnknownAssetError
from investlab.scenarios import SCENARIO_REGISTRY, UnknownScenarioError
from investlab.scenarios.framework_scenario import add_framework_arguments


def list_scenarios() -> None:
    for asset in ASSETS:
        print(f"{asset.key}\t{asset.symbol}\t{asset.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Investlab scenario runner and publisher."
    )
    add_framework_arguments(parser)

    subparsers = parser.add_subparsers(dest="command")

    scenarios_parser = subparsers.add_parser("scenarios", help="Scenario-related commands")
    scenarios_subparsers = scenarios_parser.add_subparsers(dest="scenarios_command")
    scenarios_subparsers.add_parser("list", help="List available scenario assets")

    run_parser = subparsers.add_parser("run", help="Run a scenario")
    run_subparsers = run_parser.add_subparsers(dest="run_command")
    for entry in SCENARIO_REGISTRY.entries():
        scenario_parser = run_subparsers.add_parser(entry.name, help=entry.description)
        entry.add_arguments(scenario_parser)

    publish_parser = subparsers.add_parser("publish", help="Publish-related commands")
    publish_subparsers = publish_parser.add_subparsers(dest="publish_command")
    site_parser = publish_subparsers.add_parser(
        "site", help="Build static site from scenario outputs"
    )
    site_parser.add_argument("--assets", default="all", help="逗号分隔的资产 key/code；默认 all")
    site_parser.add_argument(
        "--start-year", type=int, default=None, help="覆盖所有标的的默认起始年份"
    )
    site_parser.add_argument("--end-year", type=int, default=2025)
    site_parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("tmp"),
        help="Scenario output root (reserved for output-consuming mode)",
    )
    site_parser.add_argument(
        "--site-dir", type=Path, default=Path("dist/site"), help="Site output directory"
    )
    site_parser.add_argument(
        "--rebalance-html", type=str, default=None,
        help="Path to rebalance comparison HTML (e.g. tmp/rebalance/rebalance_comparison.html)"
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "scenarios":
            if args.scenarios_command == "list":
                list_scenarios()
                return
            parser.error("scenarios requires a subcommand")
        if args.command == "run":
            if not args.run_command:
                parser.error("run requires a subcommand")
            entry = SCENARIO_REGISTRY.get(args.run_command)
            entry.run(args)
            return
        if args.command == "publish":
            if not args.publish_command:
                parser.error("publish requires a subcommand")
            if args.publish_command == "site":
                from investlab.publish.site_builder import build_site

                raise SystemExit(build_site(args))
            parser.error(f"unknown publish command: {args.publish_command}")
        SCENARIO_REGISTRY.get("framework").run(args)
    except UnknownAssetError as error:
        parser.exit(status=1, message=f"{error}\n")
    except UnknownScenarioError as error:
        parser.exit(status=1, message=f"{error}\n")


if __name__ == "__main__":
    main()
