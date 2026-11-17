# Encore reports

Site: https://magland.github.io/encore-reports/

Readable overviews of what [Encore Science](https://encorescience.org/) found when it tried to reproduce published findings from their open data, with interactive figures made with [figpack](https://github.com/flatironinstitute/figpack).

Encore records every claim of a paper, the outcome of each attempt to reproduce it, and what the attempt learned about the data. Those records are precise but long, and the registry has no figures. Each report here takes one paper, explains the question and the result for a reader who has not read the paper, and shows the data with one or more interactive figures computed with the attempt's own code.

## Reports

- [Churchland et al. (2012): rotational dynamics during reaching](papers/churchland-2012/)
- [The International Brain Laboratory (2021): standardized and reproducible decision-making in mice](papers/ibl-2021/)

## Layout

Each paper has a directory `papers/<paper key>/`, named by its Encore paper key, with:

- `README.md`: the report.
- `compute.py`: streams the data and caches what the figures need under `cache/` (not committed).
- `fig_*.py`: one script per interactive figure. Each saves the figure locally, or uploads it to the figpack cloud with `--upload` and prints its URL.
- `plot_static.py`: draws the static plots into `images/` with matplotlib.
- `figures.json`: the URL, name, short description and embedded height of each uploaded figure.
- `images/`: the static plots, and a PNG of each interactive figure made with `tools/snapshot.sh` from its URL.
- Any code reused from the Encore entry, copied unchanged with its license.

A report uses a static plot where interaction would add nothing (a histogram, a single comparison) and an interactive figpack figure where it lets the reader see something a still image cannot, such as following one item across panels or through time. A static plot is an ordinary image in the markdown, with its caption in italics below it. An interactive figure is a linked image followed by a link that opens it in a new tab:

```markdown
[![Alt text](images/rotations.png)](https://figures.figpack.org/figures/default/<id>/index.html)

[Open the interactive figure in a new tab](https://figures.figpack.org/figures/default/<id>/index.html)
```

GitHub does not render iframes in markdown, so on GitHub the image stands in for the figure. The site at https://magland.github.io/encore-reports/ is built from the same markdown by `tools/build_site.py` (run by `.github/workflows/pages.yml` on every push to `main`): each image that links to a figpack figure is replaced by the embedded figure, at the `height` given for it in `figures.json` (default 650 px), and links to figures open in a new tab. To build it locally: `.venv/bin/python tools/build_site.py` (writes `_site/`).

## Setup

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

The figures use views from `figpack_experimental`. Until the `LinkedTrajectories` view is released, install it from the figpack branch `linked-trajectories` (`extension_packages/figpack_experimental`, after `npm install && npm run build`). Uploading needs `FIGPACK_API_KEY` in the environment. Uploaded figures expire after 24 hours unless pinned, so after uploading, record the URLs in `figures.json` and pin them with `.venv/bin/python tools/pin_figures.py papers/<paper key>/figures.json`.
