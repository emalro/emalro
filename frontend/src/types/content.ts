/**
 * Content type contracts for the emalro portfolio.
 *
 * Every localizable prose string uses the LocalizedStr shape:
 *   { es: string; en: string }
 *
 * The Spanish value is required (non-empty). The English value MAY be
 * empty, in which case the i18n resolver falls back to Spanish silently.
 *
 * This shape is enforced at build time by scripts/validate-i18n.mjs.
 */

export type LocalizedStr = { es: string; en: string };

export interface Personal {
  // Personal name is a proper noun; stored as LocalizedStr for i18n
  // symmetry even though the value is the same in both languages.
  name: LocalizedStr;
  role: LocalizedStr;
  summary: LocalizedStr;
  avatar_url: string;
  hardSkills: LocalizedStr[];
  softSkills: LocalizedStr[];
}

export interface ExperienceEntry {
  id: string;
  organization: string;
  logo_url: string;
  role: LocalizedStr;
  start_date: string; // YYYY-MM
  end_date: string | null; // null = current
  description: LocalizedStr;
}

export interface EducationEntry {
  id: string;
  institution: string;
  logo_url: string;
  degree: LocalizedStr;
  start_date: string; // YYYY-MM
  end_date: string; // YYYY-MM (always finite)
  description?: LocalizedStr;
}

export interface Project {
  id: string;
  title: LocalizedStr;
  description: LocalizedStr;
  image_url: string;
  technologies: string[];
  tags: string[];
  github_url?: string;
  demo_url?: string;
  created_at: string; // ISO date
}

export interface Course {
  id: string;
  platform: string;
  platform_logo_url: string;
  name: LocalizedStr;
  verification_url?: string;
  created_at: string;
}

export interface Social {
  linkedin: string;
  github: string;
  kaggle: string;
  tableau_public: string;
}
