// Minimal typing for the part of KaTeX the app uses.
declare module 'katex' {
  type Options = { output?: 'html' | 'mathml' | 'htmlAndMathml'; displayMode?: boolean; throwOnError?: boolean };
  const katex: { renderToString(tex: string, options?: Options): string };
  export default katex;
}
