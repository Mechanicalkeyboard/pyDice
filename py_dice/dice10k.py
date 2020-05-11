# coding=utf-8

import json

import requests
from logbook import Logger

log = Logger(__name__)
dice10k_url = "http://localhost:3000"


def call_counter(func):
    def helper(*args, **kwargs):
        helper.calls += 1
        return func(*args, **kwargs)

    helper.calls = 0
    helper.__name__ = func.__name__
    return helper


def create_game() -> dict:
    response = json.loads(requests.post(f"{dice10k_url}/games").content)
    log.debug(f"Create game response: {json.dumps(response, indent=2)}")
    return response


@call_counter
def fetch_game(game_id: str) -> dict:
    # TODO make this call less.
    log.info(f"fetch_game counter: {fetch_game.calls}")
    response = json.loads(requests.get(f"{dice10k_url}/games/{game_id}").content)
    log.debug(f"Fetch game response: {json.dumps(response, indent=2)}")
    return response


def start_game(game_id: str) -> dict:
    response = json.loads(requests.put(f"{dice10k_url}/games/{game_id}/start").content)
    log.debug(f"Start game response: {json.dumps(response, indent=2)}")
    return response


def add_player(game_id: str, name: str) -> dict:
    response = json.loads(
        requests.post(
            f"{dice10k_url}/games/{game_id}/players", json={"name": name}
        ).content
    )
    log.debug(f"Add player response: {response}")
    return response


def roll(game_id: str, user_id: str, steal: bool) -> dict:
    if steal:
        payload = {"steal": True}
    else:
        payload = {}
    response = json.loads(
        requests.post(
            f"{dice10k_url}/games/{game_id}/players/{user_id}/roll", json=payload
        ).content
    )
    log.debug(f"Roll response: {response}")
    return response


def send_keepers(game_id: str, user_id: str, picks: list) -> dict:
    response = json.loads(
        requests.post(
            f"{dice10k_url}/games/{game_id}/players/{user_id}/keep",
            json={"keepers": picks},
        ).content
    )
    log.debug(f"Keep response: {response}")
    return response


def pass_turn(game_id: str, user_id: str) -> dict:
    response = json.loads(
        requests.post(f"{dice10k_url}/games/{game_id}/players/{user_id}/pass").content
    )
    log.debug(f"Pass response: {response}")
    return response
