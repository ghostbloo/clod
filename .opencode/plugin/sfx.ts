import type { Plugin } from "@opencode-ai/plugin"

type SoundConfig = {
  [key: string]: {
    path: string;
  }
}

const soundConfig: SoundConfig = {
  "session.idle": {
    "path": "~/.claude/sounds/mew.wav"
  },
}

export const MyPlugin: Plugin = async ({ app, client, $ }) => {
  const playSound = async (path: string) => {
    await $`clod sfx play ${path}`.quiet();
  }

  return {
    event: async ({ event }) => {
      for (const [key, value] of Object.entries(soundConfig)) {
        if (event.type === key) {
          void playSound(value.path);
        }
      }
    }
  }
}
