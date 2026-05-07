import Link from 'next/link';

import { Button } from '@/components/ui/Button';

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div className="hero-number text-7xl font-black sm:text-8xl">404</div>
      <h1 className="mt-3 text-xl font-bold text-slate-100">页面不存在</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">
        抱歉，我们找不到这个地址。可能链接已失效，或比赛/球队的页面尚未生成。
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link href="/">
          <Button>回到首页</Button>
        </Link>
        <Link href="/track-record">
          <Button variant="ghost">查看战绩</Button>
        </Link>
      </div>
    </div>
  );
}
