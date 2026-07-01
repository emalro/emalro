#!/usr/bin/env node
/**
 * Build-time JSONB-shape validator for the emalro portfolio.
 *
 * Walks frontend/src/data/*.json and validates each file against its
 * corresponding JSON Schema. The LocalizedStr shape ({ es, en }) is
 * enforced on every localizable prose field.
 *
 * Wired into `npm run prebuild` so a violation blocks `npm run build`
 * and therefore blocks CI on PRs to main.
 *
 * Exit codes:
 *   0  all files conform
 *   1  at least one violation was found
 *   2  internal error (schema load failure, I/O error, etc.)
 */

import { readFile, readdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

// Draft-07 meta-schema is fully supported by Ajv 2020; we strip the
// `$schema` field from loaded schemas to avoid a strict-mismatch warning.
const Ajv = Ajv2020;

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const DATA_DIR = join(ROOT, "src", "data");
const SCHEMAS_DIR = join(DATA_DIR, "schemas");

/** Map data file basename -> schema basename. */
const FILE_TO_SCHEMA = {
  "personal.json": "personal.schema.json",
  "experience.json": "experience.schema.json",
  "education.json": "education.schema.json",
  "projects.json": "projects.schema.json",
  "courses.json": "courses.schema.json",
  "social.json": "social.schema.json",
};

/**
 * Schemas that are registered with the Ajv instance and self-tested
 * with a canonical sample, even when no matching data file exists
 * in `src/data/`. The blog schema lives in this group because blog
 * content is dynamic (DB-driven via Fase 2's public API) and won't
 * be committed as a static JSON file — but the schema itself is
 * part of the i18n-shape contract and must be exercised at every
 * build per `i18n-shape` REQ-i18n-shape-06.
 */
const STANDALONE_SCHEMAS = ["blog.schema.json", "contact.schema.json"];

/**
 * Canonical samples for the standalone schemas. Each sample is a
 * minimal valid instance that proves the schema compiles, accepts
 * a LocalizedStr on every localizable field, and rejects drift.
 */
const STANDALONE_SAMPLES = {
  "blog.schema.json": {
    title: { es: "Hola mundo", en: "Hello world" },
    content: {
      es: "# Hola\n\nBienvenido al blog.",
      en: "# Hello\n\nWelcome to the blog.",
    },
    excerpt: { es: "Hola", en: "Hello" },
    tags: ["data", "python"],
    slug: "hello-world",
    published_at: "2026-06-30T10:00:00Z",
  },
  // Mirrors the `ContactLabels` shape in
  // `frontend/src/components/contact/i18n.ts`. The schema proves
  // every label is a LocalizedStr so adding a new label without
  // the JSONB shape fails the build (per `i18n-shape`
  // REQ-i18n-shape-05).
  "contact.schema.json": {
    page: {
      eyebrow: { es: "// 05", en: "// 05" },
      heading: { es: "Contacto", en: "Contact" },
      intro: {
        es: "Dejame tu mensaje.",
        en: "Drop me a message.",
      },
      backLink: { es: "← Volver", en: "← Back" },
    },
    fields: {
      name: { es: "Nombre", en: "Name" },
      email: { es: "Email", en: "Email" },
      subject: { es: "Asunto", en: "Subject" },
      message: { es: "Mensaje", en: "Message" },
      submit: { es: "Enviar", en: "Send" },
    },
    errors: {
      required: { es: "Requerido.", en: "Required." },
      emailInvalid: { es: "Email inválido.", en: "Invalid email." },
      messageTooShort: {
        es: "Mensaje muy corto.",
        en: "Message too short.",
      },
      messageTooLong: {
        es: "Mensaje muy largo.",
        en: "Message too long.",
      },
      subjectTooLong: {
        es: "Asunto muy largo.",
        en: "Subject too long.",
      },
      nameTooLong: { es: "Nombre muy largo.", en: "Name too long." },
    },
    state: {
      success: { es: "¡Gracias!", en: "Thanks!" },
      error: { es: "Error.", en: "Error." },
      rateLimited: { es: "Demasiados intentos.", en: "Too many attempts." },
      networkError: { es: "Sin conexión.", en: "No connection." },
    },
  },
};

function jsonPointer(path) {
  if (!path) return "#";
  return "#/" + path.replace(/\./g, "/");
}

function truncate(value, max = 60) {
  const s = typeof value === "string" ? value : JSON.stringify(value);
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

function loadSchemas() {
  return readFile(
    join(SCHEMAS_DIR, "i18n-shape.schema.json"),
    "utf8",
  ).then((src) => JSON.parse(src));
}

async function main() {
  const sharedSchemaSrc = await loadSchemas();
  const ajv = new Ajv({ allErrors: true, strict: true });
  addFormats(ajv);
  ajv.addSchema(sharedSchemaSrc, "i18n-shape.schema.json");

  const entries = await readdir(DATA_DIR, { withFileTypes: true });
  const dataFiles = entries
    .filter((e) => e.isFile() && e.name.endsWith(".json"))
    .map((e) => e.name)
    .filter((name) => name in FILE_TO_SCHEMA);

  if (dataFiles.length === 0) {
    console.error("validate-i18n: no data files found in", DATA_DIR);
    process.exit(2);
  }

  let totalErrors = 0;
  for (const file of dataFiles) {
    const schemaFile = FILE_TO_SCHEMA[file];
    const [dataRaw, schemaRaw] = await Promise.all([
      readFile(join(DATA_DIR, file), "utf8"),
      readFile(join(SCHEMAS_DIR, schemaFile), "utf8"),
    ]);
    let data, schema;
    try {
      data = JSON.parse(dataRaw);
    } catch (err) {
      console.error(`✗ ${file}: invalid JSON (${err.message})`);
      totalErrors++;
      continue;
    }
    try {
      schema = JSON.parse(schemaRaw);
      delete schema.$schema; // accept draft-07 and draft-2020 schemas alike
    } catch (err) {
      console.error(`✗ ${schemaFile}: invalid JSON (${err.message})`);
      totalErrors++;
      continue;
    }

    let validate;
    try {
      validate = ajv.compile(schema);
    } catch (err) {
      console.error(`✗ ${schemaFile}: schema compile error (${err.message})`);
      totalErrors++;
      continue;
    }

    if (validate(data)) {
      console.log(`✓ ${file}`);
      continue;
    }

    console.error(`✗ ${file}  (${validate.errors.length} violation(s))`);
    for (const err of validate.errors) {
      const pointer = jsonPointer(err.instancePath);
      console.error(`    ${pointer}  ${err.message}`);
      if (err.params) console.error(`    params: ${truncate(err.params, 120)}`);
      console.error(
        `    expected shape: { "es": <non-empty string>, "en": <string> }`,
      );
    }
    totalErrors++;
  }

  if (totalErrors > 0) {
    console.error(
      `\nvalidate-i18n: ${totalErrors} file(s) failed. ` +
        `Wrap plain strings in { "es": "...", "en": "..." }.`,
    );
    process.exit(1);
  }

  // Self-test the standalone schemas (blog, etc.) against their
  // canonical samples. This proves the schema compiles and the
  // i18n-shape references resolve correctly at every build.
  for (const schemaFile of STANDALONE_SCHEMAS) {
    const schemaRaw = await readFile(join(SCHEMAS_DIR, schemaFile), "utf8");
    let schema;
    try {
      schema = JSON.parse(schemaRaw);
      delete schema.$schema;
    } catch (err) {
      console.error(`✗ ${schemaFile}: invalid JSON (${err.message})`);
      totalErrors++;
      continue;
    }
    let validate;
    try {
      validate = ajv.compile(schema);
    } catch (err) {
      console.error(
        `✗ ${schemaFile}: schema compile error (${err.message})`,
      );
      totalErrors++;
      continue;
    }
    const sample = STANDALONE_SAMPLES[schemaFile];
    if (validate(sample)) {
      console.log(`✓ ${schemaFile} (sample)`);
      continue;
    }
    console.error(
      `✗ ${schemaFile} (sample) (${validate.errors.length} violation(s))`,
    );
    for (const err of validate.errors) {
      const pointer = jsonPointer(err.instancePath);
      console.error(`    ${pointer}  ${err.message}`);
    }
    totalErrors++;
  }

  if (totalErrors > 0) {
    console.error(
      `\nvalidate-i18n: ${totalErrors} check(s) failed. ` +
        `Wrap plain strings in { "es": "...", "en": "..." }.`,
    );
    process.exit(1);
  }
  const totalChecked = dataFiles.length + STANDALONE_SCHEMAS.length;
  console.log(`\nvalidate-i18n: ${totalChecked} check(s) OK.`);
}

main().catch((err) => {
  console.error("validate-i18n: internal error:", err);
  process.exit(2);
});
