# Working repo

A scratch repo for starting work from a phone and handing it off to a bigger
machine. There is no single project here. Whatever is in the tree is here
because some session put it there.

## Directive

Iterate on the go; hand off to the cube or the laptop when the work outgrows a
phone. Sessions are short and interruptible. Optimize for picking the thread
back up somewhere else, not for finishing in one sitting.

## Conventions

- **One branch per thread of work.** Each session gets its own branch; don't
  commit straight to the default branch.
- **Commit early, push before going idle.** The session container is ephemeral
  and gets reclaimed after inactivity. Anything uncommitted is gone with it —
  push even mid-thought.
- **Keep a thread in its own directory** so unrelated threads never collide.
- **Leave the thread findable.** When stopping mid-task, say in the commit
  message what's done, what's next, and anything the diff won't show.

## Handoff

Pushing is the handoff. The other machine picks up with:

    git fetch origin && git checkout <branch>

State that matters travels in commits and commit messages. The session
transcript does not follow the work to another machine — don't leave anything
important only there.

## Skills

Plugins installed with `claude plugin install` land in the container's home
directory and disappear with it. A skill that should be present in *every*
phone session belongs in `.claude/skills/<name>/SKILL.md`, committed here.
