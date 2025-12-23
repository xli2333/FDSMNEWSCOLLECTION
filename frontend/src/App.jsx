import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, ArrowRight, X, Calendar, User, BookOpen, Sparkles, Filter } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { searchArticles, searchSql, getArticleDetail, summarizeArticle, travelTimeMachine } from './api';
import clsx from 'clsx';
import { Clock, RefreshCw } from 'lucide-react'; // Add icons

function App() {
  const [query, setQuery] = useState('');
  const [hasSearched, setHasSearched] = useState(false);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [summaryCache, setSummaryCache] = useState({});
  
  // Time Machine State
  const [timeMachineData, setTimeMachineData] = useState(null);
  const [timeMachineLoading, setTimeMachineLoading] = useState(false);
  const [targetDate, setTargetDate] = useState('');

  // 'rag' (Relevance) or 'sql' (Time/Exact)
  const [searchMode, setSearchMode] = useState('rag'); 
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const handleTimeTravel = async () => {
    setTimeMachineLoading(true);
    setTimeMachineData(null); // Reset previous result
    const data = await travelTimeMachine(targetDate);
    setTimeMachineData(data);
    setTimeMachineLoading(false);
  };

  const handleSearch = async (e) => {
    // ... existing search logic ...
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    setHasSearched(true);
    // Hide Time Machine when searching
    setTimeMachineData(null); 
    
    let data = [];
    if (searchMode === 'rag') {
        data = await searchArticles(query);
    } else {
        const s = startDate ? `${startDate}-01-01` : null;
        const e = endDate ? `${endDate}-12-31` : null;
        data = await searchSql(query, s, e);
    }
    
    console.log(`🔍 ${searchMode.toUpperCase()} Results:`, data);
    setResults(data);
    setLoading(false);
  };

  const openArticle = async (id) => {
    // 1. Check Cache First
    if (summaryCache[id]) {
        console.log(`⚡ Cache Hit for Article ${id}`);
        setSelectedArticle(summaryCache[id]);
        return;
    }

    // 2. Fetch if not in cache
    setSelectedArticle({ loading: true });
    setGeneratingSummary(true);

    const summaryData = await summarizeArticle(id);
    
    setGeneratingSummary(false);
    if (summaryData) {
        // 3. Update Cache & View
        setSummaryCache(prev => ({ ...prev, [id]: summaryData }));
        setSelectedArticle(summaryData);
    } else {
        setSelectedArticle(null); // Handle error
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 selection:bg-fudan-orange selection:text-white overflow-x-hidden">
      
      {/* --- HEADER / NAV --- */}
      <nav className="fixed top-0 w-full p-6 flex justify-between items-center z-40 mix-blend-difference text-white pointer-events-none">
        <div className="flex flex-col items-start pointer-events-auto cursor-pointer" onClick={() => {setHasSearched(false); setResults([]); setQuery('')}}>
          <img src="/mainpage_logo.png" alt="Logo" className="h-[50px] mb-2" />
          <div className="font-serif font-bold text-xl tracking-widest">复旦管院新闻稿智能体</div>
        </div>
        <div className="text-xs font-sans tracking-widest uppercase opacity-80">
          Knowledge Base System v1.0
        </div>
      </nav>

      {/* --- HERO / SEARCH SECTION --- */}
      <motion.div 
        layout
        className={clsx(
          "flex flex-col items-center w-full transition-all duration-700 ease-[0.16,1,0.3,1]",
          hasSearched ? "pt-14 pb-10 bg-white shadow-sm" : "min-h-screen justify-center pb-32" 
        )}
      >
        <motion.div layout className="w-full max-w-4xl px-8 relative z-10 flex flex-col items-center">
          {!hasSearched && (
            <motion.h1 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="font-serif text-6xl md:text-8xl font-black text-fudan-blue mb-12 tracking-tight leading-tight text-center"
            >
              洞察<br/>商业未来
            </motion.h1>
          )}

          {/* --- ACADEMIC SEARCH BLOCK --- */}
          <div className="w-full bg-white shadow-2xl relative">
            {/* Search Mode Tabs (Large Blocks) */}
            <div className="flex w-full border-b border-slate-100">
              <button
                type="button"
                onClick={() => setSearchMode('rag')}
                className={clsx(
                  "flex-1 py-5 px-8 text-sm font-bold tracking-[0.2em] transition-all duration-300 flex items-center justify-center gap-3",
                  searchMode === 'rag' 
                    ? "bg-fudan-orange text-white" 
                    : "bg-white text-slate-400 hover:bg-slate-50"
                )}
              >
                智能检索 (RAG)
              </button>
              <button
                type="button"
                onClick={() => setSearchMode('sql')}
                className={clsx(
                  "flex-1 py-5 px-8 text-sm font-bold tracking-[0.2em] transition-all duration-300 flex items-center justify-center gap-3",
                  searchMode === 'sql' 
                    ? "bg-fudan-orange text-white" 
                    : "bg-white text-slate-400 hover:bg-slate-50"
                )}
              >
                精确检索
              </button>
            </div>

            {/* Input Area */}
            <form onSubmit={handleSearch}>
                <div className="p-2 flex items-center bg-white relative z-10">
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={searchMode === 'rag' ? "输入您的疑问，探索知识边界..." : "输入标题或内容关键词..."}
                    className={clsx(
                      "flex-1 bg-transparent px-8 outline-none font-serif placeholder:text-slate-200 transition-all duration-300",
                      hasSearched ? "text-3xl py-6" : "text-3xl md:text-4xl py-10"
                    )}
                  />
                  <button 
                    type="submit" 
                    className={clsx(
                      "h-full px-12 py-10 transition-all duration-300 flex items-center justify-center bg-fudan-orange text-white hover:opacity-90"
                    )}
                  >
                    {loading ? (
                      <div className="animate-spin h-8 w-8 border-2 border-white border-t-transparent rounded-full" />
                    ) : (
                      <ArrowRight size={32} strokeWidth={1.5} />
                    )}
                  </button>
                </div>
                
                {/* Date Range Picker (Visible only in SQL mode) */}
                <AnimatePresence>
                    {searchMode === 'sql' && (
                        <motion.div 
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="bg-slate-50 border-t border-slate-100 overflow-hidden"
                        >
                            <div className="flex items-center gap-4 px-8 py-4 text-sm font-sans">
                                <span className="font-bold text-slate-400 uppercase tracking-wider text-xs">时间范围 (年份)</span>
                                <input 
                                    type="text" 
                                    placeholder="起始 (2020)" 
                                    value={startDate}
                                    onChange={(e) => setStartDate(e.target.value)}
                                    className="bg-white border border-slate-200 px-3 py-1 w-32 focus:border-fudan-orange outline-none"
                                />
                                <span className="text-slate-300">—</span>
                                <input 
                                    type="text" 
                                    placeholder="结束 (2025)" 
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="bg-white border border-slate-200 px-3 py-1 w-32 focus:border-fudan-orange outline-none"
                                />
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </form>
          </div>

          {/* --- TIME MACHINE MODULE --- */}
          {!hasSearched && (
            <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="mt-12 w-full max-w-2xl"
            >
                {/* Entrance */}
                {!timeMachineData && !timeMachineLoading && (
                    <div className="bg-white border border-slate-100 p-1 flex items-center shadow-lg transform hover:-translate-y-1 transition-transform duration-300">
                        <div className="bg-fudan-blue/5 p-4 flex items-center justify-center">
                            <Clock className="text-fudan-blue" size={24} />
                        </div>
                        <input 
                            type="text"
                            placeholder="输入日期 (如 2018-05-20) 或直接穿越..."
                            value={targetDate}
                            onChange={(e) => setTargetDate(e.target.value)}
                            className="flex-1 px-4 py-3 bg-transparent outline-none font-serif text-slate-600 placeholder:text-slate-300"
                        />
                        <button 
                            onClick={handleTimeTravel}
                            className="bg-fudan-blue text-white px-6 py-3 font-bold text-sm tracking-widest uppercase hover:bg-fudan-orange transition-colors"
                        >
                            启动时光机
                        </button>
                    </div>
                )}

                {/* Loading State */}
                {timeMachineLoading && (
                    <div className="bg-white border border-slate-100 p-8 text-center shadow-lg">
                        <div className="animate-spin w-8 h-8 border-2 border-fudan-orange border-t-transparent rounded-full mx-auto mb-4"/>
                        <p className="font-serif text-fudan-blue text-lg animate-pulse">时光隧道开启中...</p>
                    </div>
                )}

                {/* Result Card (Polaroid Style) */}
                <AnimatePresence>
                    {timeMachineData && (
                        <motion.div 
                            initial={{ scale: 0.8, opacity: 0, rotate: -5 }}
                            animate={{ scale: 1, opacity: 1, rotate: 0 }}
                            className="bg-white p-4 pb-8 shadow-2xl border border-slate-100 transform rotate-1 hover:rotate-0 transition-transform duration-500 cursor-pointer relative"
                            onClick={() => openArticle(timeMachineData.id)}
                        >
                            {/* Polaroid Image Area: 1:1 Aspect Ratio */}
                            <div className="bg-slate-100 w-full aspect-square mb-6 overflow-hidden relative border border-slate-100">
                                {timeMachineData.image_base64 ? (
                                    <img 
                                        src={`data:image/png;base64,${timeMachineData.image_base64}`} 
                                        alt="AI Generated Memory" 
                                        className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-slate-300 font-serif italic">
                                        (影像数据丢失...)
                                    </div>
                                )}
                            </div>
                            
                            <div className="px-4 text-center">
                                <h3 className="font-serif text-xl font-bold text-slate-800 mb-2 line-clamp-1">
                                    {timeMachineData.title}
                                </h3>
                                {/* Date moved below title */}
                                <div className="font-sans text-xs font-bold text-slate-400 tracking-widest uppercase mb-4">
                                    {timeMachineData.publish_date}
                                </div>
                                <p className="font-serif text-fudan-orange italic text-sm leading-relaxed">
                                    “{timeMachineData.quote}”
                                </p>
                            </div>

                            <button 
                                onClick={(e) => { e.stopPropagation(); handleTimeTravel(); }}
                                className="absolute -top-4 -right-4 bg-fudan-blue text-white p-3 rounded-full shadow-lg hover:bg-fudan-orange transition-colors"
                                title="原地刷新 (Re-roll)"
                            >
                                <RefreshCw size={16} />
                            </button>

                            {/* Reset / New Date Button */}
                            <button 
                                onClick={(e) => { e.stopPropagation(); setTimeMachineData(null); }}
                                className="absolute -top-4 right-12 bg-white text-slate-400 p-3 rounded-full shadow-lg border border-slate-200 hover:text-fudan-blue transition-colors"
                                title="输入新日期"
                            >
                                <Clock size={16} />
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>
          )}

          {!hasSearched && (
             <motion.div 
               initial={{ opacity: 0 }}
               animate={{ opacity: 1 }}
               transition={{ delay: 0.5 }}
               className="mt-16 flex items-center gap-8 text-fudan-blue/30 font-sans text-[10px] tracking-[0.3em] uppercase"
             >
               <span className="flex items-center gap-2"><div className="w-2 h-2 bg-fudan-blue"></div> FUDAN UNIVERSITY</span>
               <span className="flex items-center gap-2"><div className="w-2 h-2 bg-fudan-orange"></div> BUSINESS KNOWLEDGE</span>
               <span>RAG TECHNOLOGY</span>
             </motion.div>
          )}
        </motion.div>
      </motion.div>

      {/* --- RESULTS GRID --- */}
      <AnimatePresence>
        {hasSearched && (
          <div className="max-w-7xl mx-auto px-6 pt-16 pb-24">
            
            {/* Unified Results Grid */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-16"
            >
              {results.map((item, index) => (
                <ResultCard key={item.id} item={item} index={index} onClick={() => openArticle(item.id)} />
              ))}
            </motion.div>

            {results.length === 0 && !loading && (
              <div className="col-span-full text-center py-24 opacity-50 font-serif text-2xl">
                暂无相关内容，请尝试更具体的关键词。
              </div>
            )}
          </div>
        )}
      </AnimatePresence>

      {/* --- ARTICLE READER MODAL --- */}
      <AnimatePresence>
        {selectedArticle && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-sm"
            onClick={() => setSelectedArticle(null)}
          >
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="w-full md:w-[60vw] h-full bg-white shadow-2xl overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {/* LOADING STATE */}
              {selectedArticle.loading && (
                  <div className="h-full flex flex-col items-center justify-center p-12 text-center">
                      <motion.div 
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ 
                            opacity: [0.4, 1, 0.4],
                            scale: [1, 1.05, 1],
                          }}
                          transition={{ 
                            repeat: Infinity, 
                            duration: 2.5,
                            ease: "easeInOut"
                          }}
                          className="mb-12"
                      >
                          <img src="/logo.png" alt="Fudan Logo" className="w-32 h-32 object-contain" />
                      </motion.div>
                      <div className="space-y-4">
                        <h3 className="font-serif text-2xl font-bold text-fudan-blue">正在生成原文总结</h3>
                        <div className="flex items-center justify-center gap-1">
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    animate={{ opacity: [0, 1, 0] }}
                                    transition={{ repeat: Infinity, duration: 1.5, delay: i * 0.2 }}
                                    className="w-1.5 h-1.5 bg-fudan-orange rounded-full"
                                />
                            ))}
                        </div>
                        <p className="font-sans text-slate-400 text-[10px] tracking-[0.3em] uppercase mt-4">AI Summarizing Engine Running</p>
                      </div>
                  </div>
              )}

              {/* CONTENT STATE */}
              {!selectedArticle.loading && (
                  <div className="p-12 md:p-20 max-w-3xl mx-auto">
                    <button 
                      onClick={() => setSelectedArticle(null)}
                      className="fixed top-8 right-8 p-2 hover:bg-slate-100 rounded-full transition-colors z-50"
                    >
                      <X size={32} className="text-slate-400 hover:text-fudan-blue" />
                    </button>

                    <header className="mb-12 border-b border-slate-100 pb-12">
                      <div className="flex items-center gap-4 text-xs font-bold tracking-widest text-fudan-blue uppercase mb-6 flex-wrap">
                        <span className="px-2 py-1 bg-fudan-blue/5 rounded">{selectedArticle.source}</span>
                        <span className="flex items-center gap-1"><Calendar size={12}/> {selectedArticle.publish_date}</span>
                        
                        {selectedArticle.link && (
                            <a 
                              href={selectedArticle.link} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-slate-400 hover:text-fudan-orange transition-colors border-b border-transparent hover:border-fudan-orange ml-4"
                            >
                              <BookOpen size={12} /> 查看原文
                            </a>
                        )}

                        <span className="ml-auto flex items-center gap-1 text-fudan-orange"><Sparkles size={12}/> AI 智能浓缩</span>
                      </div>
                      <h1 className="font-serif text-4xl md:text-5xl font-black text-slate-900 leading-tight mb-8">
                        {selectedArticle.title}
                      </h1>
                    </header>

                    <article className="prose prose-lg prose-slate max-w-none 
                        prose-headings:font-serif prose-headings:font-bold prose-headings:text-fudan-blue prose-headings:mt-12 prose-headings:mb-8
                        prose-p:font-sans prose-p:text-slate-700 prose-p:leading-loose prose-p:text-justify prose-p:mb-12
                        prose-blockquote:border-l-4 prose-blockquote:border-fudan-orange prose-blockquote:bg-slate-50 prose-blockquote:py-4 prose-blockquote:px-6 prose-blockquote:font-serif prose-blockquote:italic prose-blockquote:text-slate-700 prose-blockquote:my-10
                        prose-strong:text-fudan-blue prose-strong:font-bold
                        prose-li:marker:text-fudan-orange prose-li:font-sans
                    ">
                      <ReactMarkdown>
                        {selectedArticle.summary 
                          ? selectedArticle.summary
                              .split('\n')
                              .map(line => line.trim())
                              .filter(line => line !== '')
                              .join('\n\n&nbsp;\n\n') 
                          : ''}
                      </ReactMarkdown>
                    </article>
                    
                    <div className="mt-24 pt-12 border-t border-slate-100 text-center pb-20">
                      <div className="font-serif text-2xl text-slate-300 italic mb-4">Fudan Knowledge Base</div>
                      <p className="text-xs text-slate-400 font-sans tracking-widest">
                          本导读由 AI 生成，长度约为原文的 50%-70%。
                      </p>
                    </div>
                  </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}

export default App;

function ResultCard({ item, index, onClick }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      className="group cursor-pointer flex flex-col justify-between h-full"
      onClick={onClick}
    >
      <div>
        <div className="mb-4 flex items-center gap-3 text-xs font-bold tracking-widest uppercase border-b border-fudan-blue/10 pb-2">
           {/* Source & Date Only */}
           <span className="text-fudan-blue">{item.source}</span>
           <span className="text-slate-400 ml-auto flex items-center gap-1">
              <Calendar size={10} /> {item.publish_date}
           </span>
        </div>
        
        <h3 className="font-serif text-2xl font-bold leading-snug mb-4 group-hover:text-fudan-blue transition-colors duration-300">
          {item.title}
        </h3>
        <p className="font-sans text-slate-500 text-sm leading-relaxed line-clamp-4">
          {item.snippet}
        </p>
      </div>
      <div className="mt-6 flex items-center text-xs font-bold tracking-wider text-slate-400 group-hover:text-fudan-blue transition-colors">
        READ ARTICLE <ArrowRight size={14} className="ml-2 group-hover:translate-x-1 transition-transform" />
      </div>
    </motion.div>
  );
}