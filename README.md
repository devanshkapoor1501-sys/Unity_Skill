# PolyForge

A skill that helps your AI assistant make simple 3D objects, animate a robot and build small Unity demos. You describe the idea; PolyForge provides the steps and tools to build it, check it, and give you files you can keep editing.

## Available skill

| Skill | What it helps you do |
| --- | --- |
| [PolyForge](.agents/skills/polyforge/) | Make simple objects, animate a robot and build a small 3D arena or 2D demo in Unity. |

**Early preview for Windows.** Simple robots, crates, walls, doorways, floor tiles and a survival arena work today. Supported robots can idle and walk in Unity. There is also a small 2D demo with walking animation, keyboard movement and wall collision. More game types and advanced textures are still being developed.

## Install the skill

Paste this into **Codex**, using the same installer as the [OpenAI skills catalog](https://github.com/openai/skills#installing-a-skill):

```text
$skill-installer install https://github.com/devanshkapoor1501-sys/Unity_Skill/tree/main/.agents/skills/polyforge
```

If the skill does not appear after installation, restart Codex. You need access to this GitHub repository to install it.

This installs the skill instructions. Building also needs Blender, Unity and PolyForge's local build tools on your computer. First, ask your assistant:

> Use PolyForge. Check my computer and help me set up anything missing before building.

Automatic setup and tested installation for other assistants, including Claude, are still being finished. A packaged plugin is planned.

## How you use it

1. **Describe your idea.** Say what you want to make and how it should look or play.
2. **Check the plan.** Your assistant explains what PolyForge can build and flags anything it cannot do yet.
3. **Let it build.** It creates and checks the objects, applies supported colors and materials, and puts them into Unity. If you already have supported 2D sprites, it can use those directly.
4. **Review and play.** It checks the result, shows what worked or failed, and asks you to try the game.
5. **Keep creating.** You get the Blender files and Unity project to edit and build on.

For example:

> Use PolyForge to make a blue robot, a crate and a small arena. Let me move with WASD, avoid a patrolling enemy, survive for 30 seconds and restart with R.

You can also ask for just a supported 3D object, such as a crate, without building a game.

For a 2D starting point, ask for the walking robot demo. You can also supply six 128×128 transparent sprite frames that you have permission to use. Your assistant checks whether they fit the current format before building.

Required human approval is checked before supported imports. Managed repairs keep
an evidence trail and restore the project through native reimport and checks if
verification fails. See [review and recovery](docs/review-and-recovery.md).

## Is it for you?

Try PolyForge if you want a starting point for simple Blender-to-Unity projects and are comfortable using an early preview. It still needs your feedback and playtesting. It cannot yet build any game you imagine or replace every part of making a game.

The project is free under the [Apache-2.0 license](LICENSE). Your AI assistant and other software may have their own costs or terms.

[Local setup and contributor guide](docs/development-guide.md) · [What has been tested](reports/phase-9.md)
