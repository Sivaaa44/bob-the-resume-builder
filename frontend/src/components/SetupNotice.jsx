export default function SetupNotice() {
  return (
    <section className="card setup">
      <h1>Set up your workspace</h1>
      <p className="muted">Bob needs your base resume and your facts before it can tailor anything.</p>
      <ol>
        <li>
          Import your resume. Every bullet becomes a fact Bob may use:
          <pre>bob init path/to/resume.tex</pre>
        </li>
        <li>
          Open <code>workspace/profile.yaml</code> and add what didn’t fit on the page: extra projects, metrics,
          tools, and aliases you’d defend in an interview.
        </li>
        <li>Reload this page.</li>
      </ol>
    </section>
  )
}
