#!/usr/bin/env node

import { run } from "./cli.js";
import { CliError } from "./lib/errors.js";

run().catch((error: unknown) => {
  if (error instanceof CliError) {
    process.stderr.write(error.message + "\n");
    process.exit(error.exitCode);
  }

  process.stderr.write("Unexpected error\n");
  process.exit(1);
});
