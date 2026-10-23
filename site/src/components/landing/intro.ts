// Settles once the opening count has cleared (or was skipped), so the hero's highlighter runs on a
// page the reader can see rather than under the intro.
let finish: () => void = () => {};
export const introDone = new Promise<void>((r) => { finish = r; });
export const finishIntro = () => finish();
