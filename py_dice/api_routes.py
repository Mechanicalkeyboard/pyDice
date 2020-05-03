# coding=utf-8

import json
from functools import reduce

from flask import Flask, Response, request
from logbook import Logger
from py_dice import actions, common, core, dcs, dice10k

log = Logger(__name__)


def start_api():
    game_state = {}
    flask_app = Flask(__name__)
    flask_app.config["DEBUG"] = True
    slack_client = core.create_client()

    @flask_app.route("/create", methods=["POST"])
    def create_game() -> Response:
        username = request.form["user_name"]
        game_id = dice10k.create_game()["game-id"]
        game_state[game_id] = {"game_id": game_id, "users": {}}
        game_state[game_id]["channel"] = request.form["channel_id"]
        response = slack_client.chat_postMessage(
            **dcs.message.create(
                game_id=game_id,
                channel_id=game_state[game_id]["channel"],
                message=f"@{username} started a game, click to join:",
            )
            .add_button(game_id=game_id, text="Join Game", action_id="join_game")
            .add_start_game(game_id=game_id)
            .add_start_game(game_id=game_id, auto_break=True)
            .build()
        )
        game_state[game_id]["parent_message_ts"] = response["ts"]
        return Response("", 200)

    @flask_app.route("/action", methods=["POST"])
    def action_route() -> Response:
        payload = json.loads(request.form["payload"])
        action = payload["actions"][0]["action_id"]
        game_id = common.get_game_id(payload)
        game_info = game_state[game_id]
        game_info["dice10k_state"] = dice10k.fetch_game(game_info["game_id"])
        username = payload["user"]["username"]
        if common.is_broken(game_info, username):
            game_state[game_id]["users"][username]["ice_broken"] = True

        if common.is_game_over(
            game_info=game_info,
            slack_client=slack_client,
            response_url=payload["response_url"],
        ):
            log.info("GAME OVER")
            return Response("", 200)

        elif action == "join_game":
            game_state[game_id].update(
                actions.join_game(
                    slack_client=slack_client,
                    game_info=game_info,
                    slack_user_id=payload["user"]["id"],
                    username=username,
                )
            )
            return Response("", 200)

        elif action == "pass_dice":
            core.build_game_panel(slack_client=slack_client, game_info=game_info)
            actions.pass_dice(
                slack_client=slack_client,
                game_info=game_info,
                response_url=payload["response_url"],
                username=username,
            )
            return Response("", 200)

        elif action == "pick_die":
            core.build_game_panel(slack_client=slack_client, game_info=game_info)
            game_state[game_id].update(
                actions.pick_dice(
                    slack_client=slack_client,
                    game_info=game_info,
                    response_url=payload["response_url"],
                    username=username,
                    picks=reduce(
                        common.fetch_die_val,
                        payload["actions"][0]["selected_options"],
                        [],
                    ),
                )
            )
            return Response("", 200)

        elif action == "roll_dice":
            core.build_game_panel(slack_client=slack_client, game_info=game_info)
            actions.roll_dice(
                slack_client=slack_client,
                game_info=game_info,
                response_url=payload["response_url"],
                username=username,
            )
            return Response("", 200)

        elif action == "steal_dice":
            slack_client.chat_postMessage(
                **dcs.message.create(
                    game_id=game_info["game_id"],
                    channel_id=game_info["channel"],
                    message=f"{payload['user']['username']} is trying to steal",
                )
                .in_thread(thread_id=game_info["parent_message_ts"])
                .build()
            )
            actions.steal_dice(
                slack_client=slack_client,
                game_info=game_info,
                response_url=payload["response_url"],
                username=username,
            )
            return Response("", 200)

        elif action == "start_game":
            game_state[game_id].update(
                actions.start_game(
                    slack_client=slack_client, game_info=game_info, auto_break=False
                )
            )
            return Response("", 200)

        elif action == "start_game_auto":
            game_state[game_id].update(
                actions.start_game(
                    slack_client=slack_client, game_info=game_info, auto_break=True
                )
            )
            return Response("", 200)

        else:
            log.warn("Action not recognized")
            return Response("", 404)

    @flask_app.route("/gamestate", methods=["POST"])
    def game_state_fn() -> Response:
        log.info(f"Game State: {json.dumps(game_state, indent=2)}")
        return Response(game_state, 200)

    flask_app.run()
