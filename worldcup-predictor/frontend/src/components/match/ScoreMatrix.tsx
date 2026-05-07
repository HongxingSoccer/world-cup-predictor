import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { cn } from '@/lib/utils';

interface ScoreMatrixProps {
  /** 10×10 matrix of joint probabilities (home rows × away cols). */
  matrix: number[][] | null | undefined;
}

/**
 * Probability heatmap of the 10×10 most-likely score-line grid. Cell shading
 * is keyed off the matrix's own max so even uniform distributions render
 * legibly without us guessing an absolute scale.
 */
export function ScoreMatrix({ matrix }: ScoreMatrixProps) {
  if (!matrix || matrix.length === 0) {
    return (
      <Card>
        <CardBody className="text-sm text-slate-400">暂无比分概率数据。</CardBody>
      </Card>
    );
  }

  const max = Math.max(...matrix.flat());
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">比分概率矩阵</h3>
        <span className="text-xs text-slate-400">行=主队, 列=客队</span>
      </CardHeader>
      <CardBody>
        <div
          className="grid gap-px overflow-x-auto rounded-lg bg-slate-800/80 p-px ring-1 ring-slate-700/60"
          style={{ gridTemplateColumns: `auto repeat(${matrix[0]?.length ?? 0}, minmax(2rem, 1fr))` }}
        >
          <Cell head>—</Cell>
          {matrix[0]?.map((_, j) => (
            <Cell key={`col-${j}`} head>
              {j}
            </Cell>
          ))}
          {matrix.map((row, i) => (
            <FragmentRow key={`row-${i}`} index={i} row={row} max={max} />
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-400">
          颜色越深表示该比分概率越高。完整 10×10 概率分布提供 Top10 比分推荐。
        </p>
      </CardBody>
    </Card>
  );
}

function FragmentRow({ index, row, max }: { index: number; row: number[]; max: number }) {
  return (
    <>
      <Cell head>{index}</Cell>
      {row.map((value, j) => (
        <Cell key={j} value={value} max={max} />
      ))}
    </>
  );
}

function Cell({
  head,
  value,
  max,
  children,
}: {
  head?: boolean;
  value?: number;
  max?: number;
  children?: React.ReactNode;
}) {
  if (head) {
    return (
      <div className="bg-slate-900/80 px-2 py-1 text-center text-[11px] font-semibold text-slate-400">
        {children}
      </div>
    );
  }
  const v = value ?? 0;
  const intensity = max && max > 0 ? Math.min(v / max, 1) : 0;
  return (
    <div
      className={cn(
        'px-2 py-1 text-center text-[11px] tabular-nums',
        intensity > 0.4 ? 'text-slate-950' : 'text-slate-300',
      )}
      // Cyan→amber gradient track for cell intensity: low values stay
      // muted slate, peak cells warm to amber so the modal score reads at
      // a glance without overwhelming the grid.
      style={{
        backgroundColor:
          intensity < 0.25
            ? `rgba(15, 23, 42, ${0.6 + intensity * 0.6})`
            : intensity < 0.6
            ? `rgba(34, 211, 238, ${0.18 + (intensity - 0.25) * 0.8})`
            : `rgba(251, 191, 36, ${0.45 + (intensity - 0.6) * 0.9})`,
      }}
      title={`概率 ${(v * 100).toFixed(1)}%`}
    >
      {(v * 100).toFixed(1)}
    </div>
  );
}
