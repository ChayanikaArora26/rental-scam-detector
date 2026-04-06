import { ShieldCheck, Zap, Database, AlertTriangle, Code2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const TECH = [
  "Python", "FastAPI", "sentence-transformers", "NLTK",
  "pdfplumber", "SQLite", "Anthropic Claude", "Next.js", "Tailwind CSS",
];

export default function AboutPage() {
  return (
    <div className="space-y-10">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-white">About</h1>
        <p className="text-zinc-400 max-w-2xl">
          How the Rental Scam Detector works, its limitations, and the tech stack behind it.
        </p>
      </div>

      {/* How it works */}
      <div className="grid sm:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database size={17} className="text-violet-400" />
              Reference Corpora
            </CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/8">
                  <th className="text-left py-2 text-zinc-500 font-medium">Corpus</th>
                  <th className="text-left py-2 text-zinc-500 font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <tr>
                  <td className="py-3 font-medium text-white pr-4">CUAD</td>
                  <td className="py-3 text-zinc-400">
                    510 real legal contracts, 10,667 annotated clauses (HuggingFace)
                  </td>
                </tr>
                <tr>
                  <td className="py-3 font-medium text-white pr-4">AU Baseline</td>
                  <td className="py-3 text-zinc-400">
                    NSW Residential Tenancy Agreement (NSW Fair Trading)
                  </td>
                </tr>
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap size={17} className="text-amber-400" />
              Detection Layers
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <p className="text-sm font-semibold text-white">Red-flag patterns</p>
              </div>
              <p className="text-sm text-zinc-400 pl-4">
                28 regex rules targeting payment methods (Western Union, crypto, gift cards),
                landlord unavailability, no-inspection clauses, illegal terms, and pressure tactics.
              </p>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-violet-500" />
                <p className="text-sm font-semibold text-white">Clause anomaly scoring</p>
              </div>
              <p className="text-sm text-zinc-400 pl-4">
                Sentence-transformer cosine similarity against the reference corpus. Chunks with
                no close match in any known-good lease are flagged as anomalous.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle size={17} className="text-amber-400" />
              Limitations
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-zinc-400">
            <p>
              This tool flags <em className="text-white">suspicious</em> patterns — it does not
              guarantee a listing is safe or a confirmed scam.
            </p>
            <p>Always inspect a property in person before signing or paying anything.</p>
            <p>
              For legal advice, contact{" "}
              <span className="text-white font-medium">NSW Fair Trading</span> or a tenancy
              advocacy service.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck size={17} className="text-emerald-400" />
              Activate AI Explanations
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-zinc-400">
              Set your Anthropic API key on the backend to unlock Claude-powered plain-English
              clause explanations:
            </p>
            <pre className="text-xs bg-zinc-900 border border-white/8 rounded-lg p-3 text-zinc-300 overflow-x-auto">
              {`export ANTHROPIC_API_KEY=sk-ant-...
uvicorn api:app --reload`}
            </pre>
          </CardContent>
        </Card>
      </div>

      {/* Tech stack */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Code2 size={16} className="text-zinc-500" />
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Tech Stack</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {TECH.map(t => (
            <Badge key={t} variant="outline">{t}</Badge>
          ))}
        </div>
      </div>
    </div>
  );
}
