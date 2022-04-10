# CodeRunBot (gaato bot)

## What is this

### CodeRunBot

It can run codes and render LaTeX.

### gaato bot

This is a bot for internal use that adds music playback and other functions to CodeRunBot. Also, this is for Japanese speakers.

## Privacy Policy

[here](bots/config/privacy-policy.md)

## How to run (CodeRunBot)

Set `CODERUNBOT_TOKEN` and `GOOGLE_API_KEY` in the `.env`.

### with venv

```
$ source /path/to/venv/bin/activate
$ pip install pip-tools
$ pip-sync
$ python -m bots
```

### without venv

```
$ pip install -r requirements.txt
$ python -m bots
```

## How to run (gaato bot)

Basically the same as CodeRunBot, but set `.env` to `GAATO_BOT_TOKEN` and the execution command is as follows. You also need ffmpeg.

```
$ python -m bots -g
```

## For developer

Pull requests are welcome.
Please use [pip-tools](https://github.com/jazzband/pip-tools) to manage packages.
Do not rewrite requirements.txt by hand.
