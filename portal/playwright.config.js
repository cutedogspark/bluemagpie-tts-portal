const path = require("path");

module.exports = {
  webServer: {
    command: "python3 -m http.server 9373",
    port: 9373,
    cwd: path.join(__dirname),
    reuseExistingServer: !process.env.CI,
  },
  use: {
    baseURL: "http://localhost:9373",
  },
};
