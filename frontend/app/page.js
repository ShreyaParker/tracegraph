"use client";
import { useState } from "react";
import { 
  Search, Activity, ArrowRight, ShieldAlert, Link as LinkIcon, 
  Box, BarChart3, Globe, AlertTriangle, Database, Split, 
  Download, Building, RefreshCw 
} from "lucide-react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

const RISK_COLORS = {
  CRITICAL: "bg-red-100 text-red-800 border-red-200",
  HIGH: "bg-orange-100 text-orange-800 border-orange-200",
  MEDIUM: "bg-yellow-100 text-yellow-800 border-yellow-200",
  LOW: "bg-green-100 text-green-800 border-green-200",
};

export default function Home() {
  const [address, setAddress] = useState("");
  const [chain, setChain] = useState("ethereum");
  const [loading, setLoading] = useState(false);
  const [traceData, setTraceData] = useState(null);
  const [error, setError] = useState(null);

  const handleSearch = async () => {
    if (!address.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/trace?address=${address.trim()}`);
      const json = await res.json();
      if (json.error) throw new Error(json.error);
      setTraceData(json.data || []);
    } catch (err) {
      setError(err.message);
      setTraceData([]);
    }
    setLoading(false);
  };

  const safeData = Array.isArray(traceData) ? traceData : [];
  const totalHops = safeData.length;
  const totalVolume = safeData.reduce((acc, tx) => acc + (Number(tx?.value) || 0), 0).toFixed(4);
  const gateways = safeData.filter(tx => tx?.type === "BRIDGED_TO" || tx?.type === "SWAPPED").length;
  const criticalNodes = safeData.filter(tx => tx?.riskLevel === "CRITICAL" || tx?.riskLevel === "HIGH").length;

  const groupedTrace = [];
  if (safeData.length > 0) {
    const map = new Map();
    safeData.forEach(tx => {
      const txKey = tx.txHash || `unknown-${tx.sender}-${tx.recipient}`;
      
      if (!map.has(txKey)) {
        map.set(txKey, {
          txHash: tx.txHash,
          sender: tx.sender,
          // 100% Dynamic: Only use what the database provides
          senderPlatform: tx.senderPlatform,
          outputs: []
        });
        groupedTrace.push(map.get(txKey));
      }
      
      const group = map.get(txKey);
      const isDuplicate = group.outputs.some(
        out => out.recipient === tx.recipient && out.value === tx.value && out.asset === tx.asset
      );
      
      if (!isDuplicate) {
        // Legitimate algorithmic check for Spoofed Tokens (Homoglyphs)
        let cleanAsset = tx.asset || (chain === "bitcoin" ? "BTC" : "Units");
        if (cleanAsset !== "DAI" && cleanAsset.replace(/[^\x00-\x7F]/g, "") === "DI") {
            cleanAsset = "⚠️ SPOOF DAI";
        }

        group.outputs.push({
          recipient: tx.recipient,
          // 100% Dynamic: Only use what the database provides
          recipientPlatform: tx.recipientPlatform,
          value: tx.value,
          asset: cleanAsset,
          type: tx.type,
          targetChain: tx.targetChain,
          riskLevel: tx.riskLevel,
          riskScore: tx.riskScore,
          vaspTag: tx.vaspTag,
          riskFlags: tx.riskFlags
        });
      }
    });
  }

  const generatePDF = () => {
    const doc = new jsPDF("landscape");
    
    doc.setFontSize(20);
    doc.setTextColor(37, 99, 235);
    doc.text("TraceGraph: Forensic Intelligence Report", 14, 22);
    
    doc.setFontSize(10);
    doc.setTextColor(100, 100, 100);
    doc.text(`Target Seed Address: ${address}`, 14, 32);
    doc.text(`Analysis Network: ${chain.toUpperCase()}`, 14, 38);
    doc.text(`Timestamp: ${new Date().toLocaleString()}`, 14, 44);

    const tableColumn = ["Hop", "Tx Hash", "Platform / Entity", "Recipient", "Asset", "Amount", "Risk"];
    const tableRows = [];

    let hopNumber = 1;
    groupedTrace.forEach((group) => {
      group.outputs.forEach((out) => {
        // PDF falls back to showing the raw address if no platform is found in the database
        const platformStr = group.senderPlatform ? `[${group.senderPlatform}]` : (group.sender ? group.sender.substring(0, 10) + "..." : "Unknown");
        const recStr = out.recipientPlatform ? `[${out.recipientPlatform}]` : (out.recipient ? out.recipient.substring(0, 10) + "..." : "Unknown");
        
        let pdfValue = typeof out.value === 'number' ? out.value.toFixed(4) : (out.value || "0");
        let pdfAsset = out.asset || "N/A";
        
        if (out.type === "BRIDGED_TO") {
            pdfValue = "SWAP";
            pdfAsset = out.targetChain ? out.targetChain.toUpperCase() : "BTC";
        }

        const txData = [
          `Hop ${hopNumber}`,
          group.txHash ? group.txHash.substring(0, 10) + "..." : "Unknown",
          platformStr,
          recStr,
          pdfAsset,
          pdfValue,
          out.riskLevel || "LOW"
        ];
        tableRows.push(txData);
      });
      hopNumber++;
    });

    autoTable(doc, {
      head: [tableColumn],
      body: tableRows,
      startY: 52,
      theme: 'grid',
      styles: { fontSize: 8, cellPadding: 3 },
      headStyles: { fillColor: [37, 99, 235] },
      alternateRowStyles: { fillColor: [245, 247, 250] }
    });

    doc.save(`TraceGraph_Report_${address.substring(0,6)}.pdf`);
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-800 p-4 md:p-8 font-sans relative overflow-hidden">
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-300/30 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-cyan-300/20 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-6xl mx-auto space-y-6 relative z-10">
        
        <div className="flex items-center space-x-3 text-blue-900 mt-4">
          <ShieldAlert size={36} className="text-blue-600" />
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">TRACEGRAPH</h1>
            <p className="text-xs text-blue-600 font-semibold tracking-wider">
              MAHARASHTRA CYBER CELL — BLOCKCHAIN FORENSICS UNIT
            </p>
          </div>
        </div>

        <div className="bg-white/70 p-6 rounded-2xl border border-white shadow-xl backdrop-blur-xl">
          <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-3.5 text-blue-400" size={20} />
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="w-full bg-white border border-blue-100 rounded-xl py-3 pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500/40 font-mono text-sm text-slate-700 placeholder-slate-400"
                placeholder="Enter seed wallet address (0x... or bc1...)"
              />
            </div>
            <select
              value={chain}
              onChange={(e) => setChain(e.target.value)}
              className="bg-white border border-blue-100 rounded-xl py-3 px-4 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/40 font-semibold"
            >
              <option value="ethereum">Ethereum (DeFi)</option>
              <option value="bitcoin">Bitcoin</option>
            </select>
            <button
              onClick={handleSearch}
              disabled={loading || !address.trim()}
              className="bg-blue-600 text-white hover:bg-blue-700 px-8 py-3 rounded-xl font-bold transition-all flex items-center justify-center space-x-2 shadow-lg shadow-blue-600/30 disabled:opacity-70"
            >
              {loading ? <Activity className="animate-spin" /> : <span>INITIATE TRACE</span>}
            </button>
          </div>
        </div>

        {traceData !== null && safeData.length > 0 && (
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 flex-1 w-full">
              {[
                { label: "Graph hops", value: `${groupedTrace.length}`, icon: Box, color: "blue" },
                { label: "Volume traced", value: `${totalVolume}`, icon: BarChart3, color: "emerald" },
                { label: "Swaps / Bridges", value: `${gateways}`, icon: Globe, color: "orange" },
                { label: "High-risk nodes", value: `${criticalNodes}`, icon: AlertTriangle, color: "red" },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="bg-white/70 p-5 rounded-2xl border border-white shadow-lg backdrop-blur-xl flex items-center space-x-4">
                  <div className={`p-3 rounded-xl bg-slate-100 text-slate-700`}><Icon size={22} /></div>
                  <div>
                    <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider">{label}</div>
                    <div className="text-xl font-bold text-slate-800 mt-0.5">{value}</div>
                  </div>
                </div>
              ))}
            </div>
            
            <button 
              onClick={generatePDF}
              className="bg-slate-800 hover:bg-slate-900 text-white px-6 py-4 rounded-2xl font-bold transition-all shadow-lg flex items-center space-x-2 h-full whitespace-nowrap"
            >
              <Download size={20} />
              <span>EXPORT PDF</span>
            </button>
          </div>
        )}

        {traceData !== null && safeData.length === 0 && !loading && (
          <div className="bg-white/70 p-12 rounded-2xl border border-dashed border-slate-300 shadow-md text-center max-w-2xl mx-auto space-y-4">
            <div className="w-12 h-12 bg-blue-50 rounded-full flex items-center justify-center mx-auto text-blue-500">
              <Database size={24} />
            </div>
            <h3 className="text-lg font-bold text-slate-700">No Graph Path Found</h3>
            <p className="text-sm text-slate-500">Trigger your background crawler to map out the transactions first.</p>
          </div>
        )}

        {traceData !== null && groupedTrace.length > 0 && (
          <div className="bg-white/70 p-6 sm:p-8 rounded-2xl border border-white shadow-xl backdrop-blur-xl">
            <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center uppercase border-b border-blue-100 pb-4">
              <Activity className="mr-3 text-blue-500" size={20} /> Chain of Custody Ledger
            </h2>
            <div className="space-y-6">
              {groupedTrace.map((group, index) => {
                
                const hasCritical = group.outputs.some(o => o.riskLevel === "CRITICAL" || o.asset.includes("SPOOF"));
                const hasHigh = group.outputs.some(o => o.riskLevel === "HIGH");
                const isBridge = group.outputs.some(o => o.type === "BRIDGED_TO");
                const dotColor = hasCritical ? "bg-red-500" : hasHigh ? "bg-orange-500" : isBridge ? "bg-orange-400" : "bg-blue-500";

                return (
                  <div key={index} className="flex items-start space-x-4">
                    
                    <div className="flex flex-col items-center mt-2 w-16">
                      <span className="text-xs font-black text-slate-400 mb-2">HOP {index + 1}</span>
                      <div className={`w-4 h-4 rounded-full border-4 border-white shadow-md z-10 ${dotColor}`} />
                      {index !== groupedTrace.length - 1 && <div className="w-1 h-full min-h-[100px] bg-blue-100 -mt-2" />}
                    </div>

                    <div className="flex-1 bg-white border border-blue-50 rounded-xl p-4 hover:border-blue-200 hover:shadow-md transition-all shadow-sm">
                      <div className="flex justify-between items-center mb-4 border-b border-slate-100 pb-3">
                        <span className="text-xs text-slate-500 bg-slate-50 px-3 py-1.5 rounded-md border font-mono">
                          Tx: {group.txHash ? `${group.txHash.substring(0, 32)}...` : "Unknown Hash"}
                        </span>
                        {group.outputs.length > 1 && (
                          <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded border border-blue-100 flex items-center">
                            <Split size={12} className="mr-1" />
                            {group.outputs.length} Outputs
                          </span>
                        )}
                      </div>

                      <div className="text-sm font-mono text-slate-500 mb-2 px-2 flex flex-wrap items-center gap-2">
                        <span>Sender: <span className="font-semibold text-slate-700">{group.sender}</span></span>
                        {group.senderPlatform && (
                          <span className="text-xs font-bold px-2 py-1 bg-indigo-100 text-indigo-700 rounded-md flex items-center">
                            <Building size={12} className="mr-1" /> {group.senderPlatform}
                          </span>
                        )}
                      </div>

                      <div className="space-y-2">
                        {group.outputs.map((out, outIdx) => {
                          const isInternal = group.sender === out.recipient;
                          
                          return (
                            <div key={outIdx} className={`p-3 rounded-lg border flex flex-col space-y-3 ${isInternal ? 'bg-slate-50/30 border-dashed border-slate-200' : 'bg-slate-50/70 border-slate-100'}`}>
                              <div className="flex flex-col sm:flex-row items-center justify-between text-sm font-mono space-y-2 sm:space-y-0">
                                
                                <div className="flex items-center justify-center w-full sm:w-1/4">
                                  {out.type === "BRIDGED_TO" ? (
                                    <div className="flex items-center text-orange-700 font-bold px-3 bg-orange-100 rounded-full text-xs py-1 border border-orange-200">
                                      <LinkIcon size={12} className="mr-1" /> JUMP TO {out.targetChain?.toUpperCase() || "BTC"}
                                    </div>
                                  ) : isInternal ? (
                                    <div className="flex items-center text-slate-500 text-xs font-bold">
                                      <RefreshCw size={14} className="mr-1" /> INTERNAL
                                    </div>
                                  ) : (
                                    <ArrowRight size={18} className="text-blue-400" />
                                  )}
                                </div>

                                <div className="flex flex-col items-center sm:items-end truncate w-full sm:w-2/4">
                                  <span className={`font-semibold ${out.riskLevel === "CRITICAL" || out.asset.includes("SPOOF") ? "text-red-700" : "text-blue-700"}`} title={out.recipient}>
                                    {out.recipient ? `${out.recipient.substring(0, 24)}...` : "Unknown"}
                                  </span>
                                  {out.recipientPlatform && (
                                    <span className="mt-1 text-[10px] font-bold px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded flex items-center">
                                      <Building size={10} className="mr-1" /> {out.recipientPlatform}
                                    </span>
                                  )}
                                </div>

                                <div className="w-full sm:w-1/4 flex justify-end">
                                  {out.type === "BRIDGED_TO" ? (
                                     <span className="text-orange-700 font-black bg-orange-50 px-3 py-1.5 rounded-full text-sm border border-orange-200 shadow-sm">
                                       CROSS-CHAIN SWAP
                                     </span>
                                  ) : (
                                     <span className={`font-black px-3 py-1.5 rounded-full text-sm border shadow-sm whitespace-nowrap ${out.asset.includes("SPOOF") ? 'bg-red-100 text-red-800 border-red-200' : 'bg-emerald-100 text-emerald-700 border-emerald-200'}`}>
                                       {typeof out.value === 'number' ? out.value.toFixed(4) : out.value} {out.asset}
                                     </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}