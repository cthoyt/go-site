#!/usr/bin/env python3

import click
import yaml
import subprocess
import glob
import os
import collections
import multiprocessing
import time
import shutil
import gzip
import json

from typing import List, Dict


@click.group()
def cli():
    pass

@cli.command()
@click.argument("group")
@click.option("--datasets", "-d", type=click.Path(exists=True, file_okay=False), required=True, help="Path to directory with all the dataset yamls")
@click.option("--target", "-T", type=click.Path(exists=False), required=True, help="Path to directory where files will be stored")
@click.option("--contexts", "-c", type=click.Path(exists=True, dir_okay=False), required=True, multiple=True)
@click.option("--ontology", "-o", type=click.Path(exists=True), required=True)
@click.option("--gafs", "-g", type=click.Path(exists=True, file_okay=False), help="Directory where to find dataset gafs")
@click.option("--gaferencer", type=click.Path(exists=True, dir_okay=False), help="Path to gaferencer if not in local path.")
@click.option("--excludes", "-x", multiple=True, help="Any dataset to exclude from processing in the group")
@click.option("--dryrun", default=False, is_flag=True)
def group(group, datasets, target, contexts, ontology, gafs, gaferencer, excludes, dryrun):
    group_dataset = list(filter(lambda r: r["id"]==group, load_resource_metadata(datasets)))
    if len(group_dataset) == 0:
        raise click.ClickException("No Resource group with the name {}".format(group))

    possible_paths = construct_gaf_paths(gafs, group_dataset[0], excludes)

    out_paths = []
    all_gaferences = []
    for path in possible_paths:
        zipped = "{path}.gz".format(path=path)
        if not os.path.exists(zipped) and not os.path.exists(path):
            # Then that dataset is not present for whatever reason. resultJust skip.
            click.echo("WARNING: skipping gaferencer on {}: GAF does not exist.".format(path))
            continue

        if os.path.exists(zipped):
            # Then we need to unzip
            unzip(zipped, path)

        name = os.path.basename(path).split("-src")[0]
        out = os.path.join(target, "{}.gaferences.json".format(name))

        # At this point we have an unzipped gaf
        success, result = run_gaferencer(contexts, ontology, path, out, dryrun=dryrun)
        if not success:
            raise click.ClickException("Gaferencer Failed: {}".format(result))

        out_paths.append(result)

    if not dryrun:
        for path in out_paths:
            with open(path) as out_file:
                outjson = json.load(out_file)
                all_gaferences.extend(outjson)


        with open(os.path.join(target, "{}.gaferences.json".format(group)), "w") as group_gaference:
            group_gaference.write(json.dumps(all_gaferences, indent=4))


def unzip(path, target):
    click.echo("Unzipping {}".format(path))
    def chunk_gen():
        with gzip.open(path, "rb") as p:
            while True:
                chunk = p.read(size=512 * 1024)
                if not chunk:
                    break
                yield chunk

    with open(target, "wb") as tf:
        with click.progressbar(iterable=chunk_gen()) as chunks:
            for chunk in chunks:
                tf.write(chunk)

def construct_gaf_paths(gaf_dir, group_dataset, excludes):
    gaf_paths = []
    datasets = [dataset for dataset in group_dataset["datasets"] if dataset["type"] == "gaf" and not dataset.get("exclude", False) and dataset["dataset"] not in excludes]
    for dataset in datasets:
        path = os.path.join(gaf_dir, "{dataset}-src.gaf".format(dataset=dataset["dataset"]))
        gaf_paths.append(path)

    return gaf_paths

def construct_context_options(contexts):
    contexts_options = " ".join(["--contexts {c}".format(c=c) for c in contexts])

    return contexts_options

def load_resource_metadata(datasets_dir) -> List[Dict]:
    """
    Loads all the YAML files in `datasets_dir` as dicts in a list.
    """
    dataset_paths = glob.glob(os.path.join(datasets_dir, "*.yaml"))
    loaded_yamls = []
    for path in dataset_paths:
        with open(path) as dataset_file:
            dataset = dict()
            if getattr(yaml, "FullLoader", None) == None:
                # We're in PyYaml < 5.1
                dataset = yaml.load(dataset_file)
            else:
                dataset = yaml.load(dataset_file, Loader=yaml.FullLoader)

            loaded_yamls.append(dataset)

    return loaded_yamls


def run_gaferencer(contexts, ontology_path, gaf_path, out_path, dryrun=False) -> str:
    """
    Does the download with wget in a subprocess
    Result is a tuple of (bool, path OR error message). The first element is
    a bool indicating succcessful completion of the process with True, and False
    if not. If successful, the secend element is the path downloaded. Otherwise
    it's whatever standard error was from wget.
    """
    contexts_options = construct_context_options(contexts)
    gaferencer_command = "gaferencer gaf --ontfile true {contexts_options} --ontology-iri {ontology} --gaf-file {gaf} --inferred-annotations-outfile {out}".format(contexts_options=contexts_options, ontology=ontology_path, gaf=gaf_path, out=out_path)

    click.echo("running gaferencer with: `{}`".format(gaferencer_command))
    result = (True, out_path)
    if not dryrun:
        p = subprocess.Popen(gaferencer_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        exit_code = p.wait()  # This is probably redundant, but will return the exit code
        if exit_code != 0:
            result = (False, err.decode("utf-8"))
        else:
            result = (True, out_path)
            # Somehow actually verify the the file is correct?
    return result


if __name__ == "__main__":
    cli()
