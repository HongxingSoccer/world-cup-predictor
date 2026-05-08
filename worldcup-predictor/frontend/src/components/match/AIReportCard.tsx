'use client';

import { Sparkles } from 'lucide-react';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';

interface ReportPayload {
  title?: string;
  summary?: string | null;
  contentMd?: string | null;
  content_md?: string | null;
  modelUsed?: string | null;
  model_used?: string | null;
  publishedAt?: string | null;
  published_at?: string | null;
}

interface Props {
  report: ReportPayload | null;
}

/**
 * AI match-analysis card. Falls back to a "report not yet generated"
 * empty state when the source row is missing — pre-launch we expect this
 * to be the common case until the LLM client is configured.
 */
export function AIReportCard({ report }: Props) {
  const t = useT();
  const title = report?.title;
  const summary = report?.summary ?? '';
  const body = report?.contentMd ?? report?.content_md ?? '';
  const modelUsed = report?.modelUsed ?? report?.model_used ?? null;
  const publishedAt = report?.publishedAt ?? report?.published_at ?? null;

  if (!report || !title) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-amber-300" />
            <h3 className="text-sm font-semibold text-slate-100">{t('match.aiAnalysis')}</h3>
          </div>
          <span className="text-xs text-slate-400">{t('match.unpublished')}</span>
        </CardHeader>
        <CardBody>
          <p className="text-sm leading-relaxed text-slate-400">{t('match.aiNotGenerated')}</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-amber-300" />
          <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
        </div>
        <div className="text-right text-xs text-slate-400">
          {modelUsed ? <div>{modelUsed}</div> : null}
          {publishedAt ? (
            <div className="tabular-nums">
              {new Date(publishedAt).toLocaleDateString('zh-CN')}
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardBody>
        {summary ? (
          <p className="mb-3 rounded-lg border border-slate-800/70 bg-slate-900/40 px-3 py-2 text-sm leading-relaxed text-slate-200">
            {summary}
          </p>
        ) : null}
        <article
          className={[
            'prose prose-invert prose-sm max-w-none',
            'prose-headings:text-slate-100 prose-headings:font-semibold',
            'prose-p:text-slate-300 prose-p:leading-relaxed',
            'prose-strong:text-slate-100 prose-li:text-slate-300',
            'prose-h2:mt-5 prose-h2:text-base prose-h2:text-cyan-300',
          ].join(' ')}
        >
          {/* Reports are markdown with light formatting; we render line-by-line
              instead of pulling in a full MD parser to keep the bundle slim. */}
          {body.split(/\n+/).map((line, idx) => renderLine(line, idx))}
        </article>
      </CardBody>
    </Card>
  );
}

function renderLine(line: string, idx: number) {
  const trimmed = line.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('# ')) {
    return (
      <h2 key={idx} className="text-base font-semibold text-cyan-300">
        {trimmed.slice(2)}
      </h2>
    );
  }
  if (trimmed.startsWith('## ')) {
    return (
      <h3 key={idx} className="mt-4 text-sm font-semibold text-cyan-300">
        {trimmed.slice(3)}
      </h3>
    );
  }
  if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
    return (
      <li key={idx} className="ml-5 list-disc text-slate-300">
        {trimmed.slice(2)}
      </li>
    );
  }
  return (
    <p key={idx} className="text-sm leading-relaxed text-slate-300">
      {trimmed}
    </p>
  );
}
