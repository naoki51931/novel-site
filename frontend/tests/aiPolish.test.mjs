import assert from "node:assert/strict";
import { applyPolishReplacement, buildPolishPrompt } from "../src/lib/aiPolish.mjs";

const prompt = buildPolishPrompt({
  baseBody: "本文",
  tone: "軽快",
  genre: "恋愛",
  characters: "AとB",
  isR18: false,
  intensity: 80,
  maxChars: 1234,
});

assert.ok(prompt.includes("最大文字数: 1234字以内"));
assert.ok(prompt.includes("添削の強さ:"));
assert.ok(prompt.includes("【本文】"));

const replaced = applyPolishReplacement("abc123xyz", 3, 6, "DEF");
assert.equal(replaced, "abcDEFxyz");

const clamped = applyPolishReplacement("abc", -5, 10, "Z");
assert.equal(clamped, "Z");

console.log("aiPolish tests passed");
