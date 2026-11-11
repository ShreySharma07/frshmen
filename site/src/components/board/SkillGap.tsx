// The top skills your matching jobs ask for that your saved resume doesn't name, and why each
// matters: how many of those jobs ask for it.
import Link from "next/link";

export function SkillGap({ missing, total }: { missing: { skill: string; n: number }[]; total: number }) {
  return (
    <section className="rounded-lg border border-line p-4">
      <h2 className="text-meta font-medium uppercase tracking-wide text-muted">Skill gap</h2>
      {missing.length === 0 ? (
        <p className="mt-3 text-body text-muted">Your resume names every skill your matches ask for most. Nice.</p>
      ) : (
        <ol className="mt-3 space-y-2.5">
          {missing.map(({ skill, n }) => (
            <li key={skill} className="text-body">
              <span className="font-medium">{skill}</span>
              <span className="block text-meta text-muted">
                Asked in {Math.round((n / Math.max(total, 1)) * 100)}% of the {total.toLocaleString("en-IN")} jobs that fit you. If you have it, put it on your resume.
              </span>
            </li>
          ))}
        </ol>
      )}
      <Link href="/insights" className="mt-3 inline-block text-meta font-medium text-accent-text underline underline-offset-2">All skills</Link>
    </section>
  );
}
