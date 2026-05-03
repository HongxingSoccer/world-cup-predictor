export function Footer() {
  return (
    <footer className="mt-12 border-t border-slate-200 bg-white text-sm text-slate-500">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-6 md:flex-row md:items-center md:justify-between">
        <div>© {new Date().getFullYear()} WCP · 世界杯预测</div>
        <nav className="flex gap-4">
          <a href="/about" className="hover:text-slate-700">
            关于
          </a>
          <a href="/terms" className="hover:text-slate-700">
            服务条款
          </a>
          <a href="/privacy" className="hover:text-slate-700">
            隐私政策
          </a>
        </nav>
      </div>
    </footer>
  );
}
