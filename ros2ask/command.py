import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from ros2cli.command import CommandExtension


SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'kind': {'type': 'string', 'enum': ['run', 'done']},
        'argv': {'type': 'array', 'items': {'type': 'string'}},
        'capture': {'type': 'boolean'},
        'message': {'type': 'string'},
    },
    'required': ['kind', 'argv', 'capture', 'message'],
}

MAX_STEPS = 8
MAX_OUTPUT = 12000
ALLOWED_PROGRAMS = {'ros2', 'colcon', 'rosdep'}


def _plan(request, history):
    prompt = (
        'You control ROS 2 Lyrical through a command runner. '
        'Return exactly one JSON action matching the supplied schema. '
        'Do not run commands or use tools yourself. '
        'For a run action, argv must be an argument array beginning with ros2, colcon, or rosdep. '
        'Never use a shell, ros2 ask, or interactive prompts. '
        'Use capture=true for short inspection commands whose output you need for another step. '
        'Use capture=false for the final operation, including long-running commands; '
        'its output will stream to the user and Ctrl-C will stop it. '
        'For /cmd_vel publishing, always use a finite number of messages with --times '
        'and add -w 0 to avoid waiting for subscribers. '
        'If a request is ambiguous, choose a reasonable ROS default. '
        'Return kind=done only when there is no more operation to perform. '
        'Use empty argv and capture=false for done. '
        'Do not merely describe a command when you can run it.\n'
        f'User request: {json.dumps(request, ensure_ascii=False)}\n'
        f'Previous commands and results: {json.dumps(history, ensure_ascii=False)}'
    )
    with tempfile.TemporaryDirectory(prefix='ros2ask-') as directory:
        schema_path = Path(directory, 'schema.json')
        result_path = Path(directory, 'result.json')
        schema_path.write_text(json.dumps(SCHEMA), encoding='utf-8')
        planner = os.environ.get('ROS2_ASK_PLANNER', 'codex')
        command = [
            planner, 'exec', '--sandbox', 'read-only', '--ephemeral',
            '--skip-git-repo-check', '--ignore-user-config',
            '--output-schema', str(schema_path),
            '--output-last-message', str(result_path), '-',
        ]
        completed = subprocess.run(
            command, input=prompt, text=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, timeout=120, cwd=directory,
        )
        if completed.returncode:
            raise RuntimeError(
                f'Codex failed ({completed.returncode}): '
                f'{completed.stderr[-2000:]}')
        return json.loads(result_path.read_text(encoding='utf-8'))


def _validate(action):
    if not isinstance(action, dict) or set(action) != set(SCHEMA['required']):
        raise ValueError('Codex returned an invalid action')
    if action['kind'] not in ('run', 'done'):
        raise ValueError('Codex returned an unknown action')
    if not isinstance(action['argv'], list) or not all(
            isinstance(part, str) and part and len(part) <= 4096
            for part in action['argv']):
        raise ValueError('Codex returned invalid command arguments')
    if not isinstance(action['capture'], bool) or not isinstance(action['message'], str):
        raise ValueError('Codex returned invalid action fields')
    if action['kind'] == 'done':
        if action['argv']:
            raise ValueError('A done action cannot contain a command')
        return
    argv = action['argv']
    if not argv or argv[0] not in ALLOWED_PROGRAMS:
        raise ValueError('Only ROS tools can be executed')
    if argv[:2] == ['ros2', 'ask']:
        raise ValueError('Recursive ros2 ask is not allowed')
    if argv[:3] == ['ros2', 'topic', 'pub'] and '/cmd_vel' in argv:
        if not any(part in ('-t', '--times', '-1', '--once') for part in argv):
            raise ValueError('/cmd_vel publishing must have a finite count')


def _execute(action):
    argv = action['argv']
    print('+ ' + shlex.join(argv), flush=True)
    if action['capture']:
        completed = subprocess.run(argv, text=True, capture_output=True, timeout=30)
        output = (completed.stdout + completed.stderr)[-MAX_OUTPUT:]
        if output:
            print(output, end='' if output.endswith('\n') else '\n', flush=True)
        return completed.returncode, output
    completed = subprocess.run(argv)
    return completed.returncode, ''


class AskCommand(CommandExtension):
    """Execute a ROS operation described in natural language."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument('text', help='ROS operation to perform')

    def main(self, *, parser, args):
        history = []
        try:
            for _ in range(MAX_STEPS):
                action = _plan(args.text, history)
                _validate(action)
                if action['kind'] == 'done':
                    if action['message']:
                        print(action['message'])
                    return 0
                status, output = _execute(action)
                if not action['capture']:
                    return status
                history.append({
                    'argv': action['argv'], 'exit_code': status, 'output': output,
                })
            print('Stopped after too many steps', file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            return 130
        except (OSError, subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as error:
            print(f'ros2 ask: {error}', file=sys.stderr)
            return 1
