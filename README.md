# ⚠️ Just idea, 100% vibe coding, no-review, as-is🙏

# ros2ask

A small ROS 2 CLI extension that turns `ros2 ask "..."` into a direct ROS operation. Codex chooses a command, and `ros2ask` runs it in the current ROS environment. Short inspection commands can feed a follow-up command. Long-running commands stream output until stopped with Ctrl-C.

## Requirements

- ROS 2 Lyrical and `colcon`
- Codex CLI installed and logged in (`codex login status`)

## Build

Place this repository under `src/` in a ROS 2 workspace, then run:

```bash
source /opt/ros/lyrical/setup.bash
colcon build --packages-select ros2ask --symlink-install
source install/setup.bash
```

## Use

```bash
ros2 ask "topicの一覧を表示して"
ros2 ask "cmd_velをsubscribeして受信したTwistを表示し続けて"
ros2 ask "x=0.5でcmd_velを1hzで10回pub"
```

The extension currently runs commands beginning with `ros2`, `colcon`, or `rosdep`. It prints each command before execution and passes arguments without a shell. Publishing to `/cmd_vel` requires a finite message count.
