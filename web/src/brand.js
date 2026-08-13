/** Ichki texnik nomlarni ("ollama", "qwen2.5-coder"...) foydalanuvchiga
 * ko'rinadigan brend nomiga o'giradi — xom provider/model ID hech qachon
 * ekranga chiqmasligi uchun.
 */

const PROVIDER_LABELS = { ollama: "5code" };
const MODEL_LABELS = { qwen: "5code_pro" };

export function brandProvider(provider) {
  return PROVIDER_LABELS[provider] ?? provider;
}

export function brandModel(model) {
  if (!model) return model;
  const bare = model.split(":")[0].toLowerCase();
  for (const [prefix, label] of Object.entries(MODEL_LABELS)) {
    if (bare.startsWith(prefix)) return label;
  }
  return model;
}
