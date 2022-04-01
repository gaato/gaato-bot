# がーとぼっと

**This repository is for Japanese.**

## What is this

音楽を再生したり TeX を画像化したりする Discord の bot です。

## How to run

.env に `DISCORD_TOKEN` と `GOOGLE_API_KEY` を設定する。

**以下の作業は venv の中でやってください！**

```
$ pip install pip-tools
$ pip-sync
$ python -m bots
```

## For developer

プルリクエストは歓迎します。
パッケージの管理は [pip-tools](https://github.com/jazzband/pip-tools) を使ってください。
requirements.txt を手で書き換えることはしないでください。
