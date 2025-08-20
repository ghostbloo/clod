import type { Hooks, Plugin } from "@opencode-ai/plugin"

type SoundEntry = string | { path: string };

type SoundPack = {
  $schema?: string;
  version?: number;
  baseDir?: string;
  opencode?: {
    events?: Record<string, SoundEntry>;
    hooks?: Record<string, SoundEntry>;
  };
  claude?: Record<string, Record<string, SoundEntry>>;
}

type SoundConfig = {
  events: Record<string, { path: string }>
  hooks: Record<string, { path: string }>
}

const DEFAULT_BASE_DIR = "~/.claude/sounds";

const normalizePath = (baseDir: string, entry: SoundEntry): string => {
  const raw = typeof entry === "string" ? entry : entry.path;
  if (!raw) {
    return "";
  }
  // If absolute or tilde path, return as-is
  if (raw.startsWith("/") || raw.startsWith("~")) {
    return raw;
  }
  // Otherwise join with baseDir
  if (baseDir.endsWith("/")) {
    return baseDir + raw;
  }
  return baseDir + "/" + raw;
}

const expandTilde = (p: string): string => {
  if (p.startsWith("~")) {
    const home = (globalThis as any).process?.env?.HOME;
    if (home) {
      return p.replace(/^~/, home);
    }
  }
  return p;
}

const loadSoundPack = async (paths: string[]): Promise<SoundPack | null> => {
  for (const p of paths) {
    try {
      const file = Bun.file(expandTilde(p));
      // Attempt to read; if it fails, continue
      const data = await file.json();
      if (data && typeof data === "object") {
        return data as SoundPack;
      }
    } catch (_e) {
      // ignore and try next
    }
  }
  return null;
}

const buildConfigFromPack = (pack: SoundPack | null): SoundConfig => {
  const baseDir = pack?.baseDir || DEFAULT_BASE_DIR;
  const events: Record<string, { path: string }> = {};
  const hooks: Record<string, { path: string }> = {};

  if (pack?.opencode?.events) {
    for (const [eventType, entry] of Object.entries(pack.opencode.events)) {
      const path = normalizePath(baseDir, entry);
      if (path) {
        events[eventType] = { path };
      }
    }
  }

  if (pack?.opencode?.hooks) {
    for (const [hookName, entry] of Object.entries(pack.opencode.hooks)) {
      const path = normalizePath(baseDir, entry);
      if (path) {
        hooks[hookName] = { path };
      }
    }
  }

  // Provide a sensible default if nothing configured
  if (Object.keys(events).length === 0 && Object.keys(hooks).length === 0) {
    events["session.idle"] = {
      path: `${DEFAULT_BASE_DIR}/mew.wav`,
    };
  }

  return { events, hooks };
}

const toClodArg = (fullPath: string): string => {
  // clod sfx play expects a filename in ~/.claude/sounds
  const home = (globalThis as any).process?.env?.HOME || "";
  const prefixes = [
    "~/.claude/sounds/",
    home ? `${home}/.claude/sounds/` : undefined,
  ].filter(Boolean) as string[];
  for (const prefix of prefixes) {
    if (fullPath.startsWith(prefix)) {
      return fullPath.slice(prefix.length);
    }
  }
  // Fallback to basename
  const parts = fullPath.split("/");
  return parts[parts.length - 1] || fullPath;
}

export const MyPlugin: Plugin = async ({ app, client, $ }) => {
  const pack = await loadSoundPack([
    `${app.path.root}/.opencode/soundpack.json`,
    `${app.path.config}/soundpack.json`,
    `~/.claude/soundpack.json`,
  ]);
  const soundConfig = buildConfigFromPack(pack);

  const playSound = async (path: string) => {
    const arg = toClodArg(path);
    await $`clod sfx play ${arg} &`.quiet();
  }

  const hooks: Hooks = {
    event: async ({ event }) => {
      const cfg = soundConfig.events[event.type];
      if (cfg?.path) {
        void playSound(cfg.path);
      }
    },
    "tool.execute.before": async (_input, _output) => {
      const cfg = soundConfig.hooks["tool.execute.before"];
      if (cfg?.path) {
        void playSound(cfg.path);
      }
    },
    "tool.execute.after": async (_input, _output) => {
      const cfg = soundConfig.hooks["tool.execute.after"];
      if (cfg?.path) {
        void playSound(cfg.path);
      }
    },
    "permission.ask": async (_input, _output) => {
      const cfg = soundConfig.hooks["permission.ask"];
      if (cfg?.path) {
        void playSound(cfg.path);
      }
    },
    "chat.message": async (_input, _output) => {
      const cfg = soundConfig.hooks["chat.message"];
      if (cfg?.path) {
        void playSound(cfg.path);
      }
    },
  };

  return hooks;
}
