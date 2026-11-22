// Prettier settings (OCA defaults). The XML plugin formats Odoo views and data files.
// require.resolve finds the plugin inside pre-commit's own Node environment.
/** @type {import('prettier').Config} */
const config = {
  bracketSpacing: false,
  printWidth: 88,
  proseWrap: "always",
  semi: true,
  trailingComma: "es5",
  xmlWhitespaceSensitivity: "strict",
  plugins: [require.resolve("@prettier/plugin-xml")],
};

module.exports = config;
