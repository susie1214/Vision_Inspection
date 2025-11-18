// import { useEffect, useRef, useState } from "react";
// import { Stage, Layer, Rect, Image as KImage } from "react-konva";
// import useImage from "use-image";
// import { listImages, getAnns, saveAnns } from "./api";
// import { useLabStore } from "./store";

// function Img({ url }) {
//   const [img] = useImage(url, "anonymous");
//   return <KImage image={img} />;
// }

// export default function App(){
//   const [images, setImages] = useState([]);
//   const [drawing, setDrawing] = useState(false);
//   const stageRef = useRef();

//   const { image, setImage, anns, loadAnns, addBBox, updateBBox, undo, redo } = useLabStore();

//   useEffect(()=>{ listImages().then(setImages); },[]);
//   useEffect(()=>{ if(image) getAnns(image.id).then(loadAnns); },[image]);

//   const down = e=>{
//     if(!image) return;
//     const pos = e.target.getStage().getPointerPosition();
//     useLabStore.getState().snapshot();
//     setDrawing({ x: pos.x, y: pos.y, w: 0, h: 0 });
//   };
//   const move = e=>{
//     if(!drawing) return;
//     const pos = e.target.getStage().getPointerPosition();
//     setDrawing(s=>({ ...s, w: pos.x - s.x, h: pos.y - s.y }));
//   };
//   const up = ()=>{
//     if(!drawing) return;
//     const { x,y,w,h } = drawing;
//     if(Math.abs(w)>3 && Math.abs(h)>3) addBBox([x,y,w,h]);
//     setDrawing(false);
//   };

//   const save = async ()=>{
//     if(!image) return;
//     await saveAnns(anns);
//     alert("saved");
//   };

//   const stageW = window.innerWidth-280, stageH = window.innerHeight;

//   return (
//     <div style={{display:"grid", gridTemplateColumns:"280px 1fr", height:"100vh"}}>
//       <aside style={{padding:12, borderRight:"1px solid #ddd"}}>
//         <h3>Images</h3>
//         <div style={{overflowY:"auto", maxHeight:"40vh"}}>
//           {images.map(it=>(
//             <div key={it.id}
//               onClick={()=> setImage(it)}
//               style={{padding:6, cursor:"pointer", background:image?.id===it.id?"#eef":"transparent"}}>
//               {it.filename}
//             </div>
//           ))}
//         </div>
//         <hr/>
//         <button onClick={undo}>Undo</button>
//         <button onClick={redo} style={{marginLeft:8}}>Redo</button>
//         <button onClick={save} style={{marginLeft:8}}>Save</button>
//         <p style={{marginTop:12}}>Drag on canvas to draw a box.</p>
//         <ul>
//           {anns.map((a,i)=><li key={i}>{a.label} [{a.bbox?.map(v=>v.toFixed?.(0)??v).join(", ")}]</li>)}
//         </ul>
//       </aside>

//       <main>
//         <Stage width={stageW} height={stageH} onMouseDown={down} onMouseMove={move} onMouseUp={up}>
//           <Layer>
//             {image && <Img url={`http://localhost:8000${image.url}`} />}
//             {anns.map((a,i)=> a.atype==="bbox" && (
//               <Rect key={i}
//                 x={a.bbox[0]} y={a.bbox[1]} width={a.bbox[2]} height={a.bbox[3]}
//                 stroke="black" draggable
//                 onDragMove={e=>{
//                   const {x,y} = e.target.position();
//                   updateBBox(i, [x,y,a.bbox[2],a.bbox[3]]);
//                 }}
//                 onTransformEnd={e=>{
//                   const node = e.target;
//                   const w = node.width()*node.scaleX();
//                   const h = node.height()*node.scaleY();
//                   node.scaleX(1); node.scaleY(1);
//                   updateBBox(i, [node.x(), node.y(), w, h]);
//                 }}
//               />
//             ))}
//             {drawing && <Rect x={drawing.x} y={drawing.y} width={drawing.w} height={drawing.h} stroke="red" dash={[4,4]} />}
//           </Layer>
//         </Stage>
//       </main>
//     </div>
//   );
// }

import React, { useEffect, useMemo, useRef, useState } from "react";

/* ========= 설정 ========= */
const IMAGE_PATH = "/dataset/images/";   // public 아래 권장
const IMAGE_EXT  = ".jpg";
const DEFAULT_FILES = Array.from({length:100},(_,i)=>`${String(i+1).padStart(3,"0")}${IMAGE_EXT}`);

const DEFAULT_CATEGORIES = [
  { id: 1, name: "hole",    supercategory: "" },
  { id: 2, name: "burr",    supercategory: "" },
  { id: 3, name: "scratch", supercategory: "" },
];

/* 카테고리 색상 팔레트(안정적 매핑) */
const PALETTE = [
  "#e11d48","#2563eb","#059669","#f59e0b","#7c3aed","#0ea5e9",
  "#84cc16","#f43f5e","#06b6d4","#a855f7","#22c55e","#d946ef",
];
const colorOf = (catId) => PALETTE[(catId-1) % PALETTE.length];

const emptyMeta = (desc="") => ({
  licenses:[{name:"",id:0,url:""}],
  info:{contributor:"",date_created:"",description:desc,url:"",version:"",year:""}
});

const dl = (obj,fn) => {
  const b = new Blob([JSON.stringify(obj,null,2)],{type:"application/json"});
  const u = URL.createObjectURL(b); const a = document.createElement("a");
  a.href=u; a.download=fn; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(u);
};

let gAnnId = 1;

export default function App(){
  /* 상태 */
  const [projectName,setProjectName] = useState("VISION-Project");
  const [categories,setCategories]   = useState(DEFAULT_CATEGORIES);
  const [files,setFiles]             = useState(DEFAULT_FILES);
  const [curIdx,setCurIdx]           = useState(0);  // files[curIdx]

  const [mode,setMode] = useState("rect");          // "rect" | "poly"
  const [scale,setScale] = useState(1);
  const [brightness,setBrightness] = useState(100);

  // 메타/어노
  const [imagesMeta,setImagesMeta] = useState({});  // file -> meta
  const [annByImage,setAnnByImage] = useState({});  // file -> [anns]
  const [history,setHistory]       = useState({});  // file -> stack of snapshots

  // 현재 선택 클래스
  const [currentCat,setCurrentCat] = useState(DEFAULT_CATEGORIES[0].id);

  // 폴리곤 그리기
  const [polyPts,setPolyPts]       = useState([]);  // [{x,y},...]
  const [polyActive,setPolyActive] = useState(false);

  // Rect 그리기
  const drawing = useRef(false);
  const startPt = useRef({x:0,y:0});

  const imgRef  = useRef(null);
  const svgRef  = useRef(null);

  const fileName = files[curIdx] || "";
  const meta     = imagesMeta[fileName] || null;
  const anns     = annByImage[fileName] || [];

  /* 이미지 로드 시 메타 기록 */
  useEffect(()=>{
    const img = imgRef.current; if(!img || !fileName) return;
    const onLoad = ()=>{
      setImagesMeta(prev=>({
        ...prev,
        [fileName]:{
          id: parseInt(fileName.split(".")[0],10) || (Object.keys(prev).length+1),
          file_name:fileName,
          width: img.naturalWidth,
          height: img.naturalHeight,
          license:0,flickr_url:"",coco_url:"",date_captured:0
        }
      }));
    };
    img.addEventListener("load", onLoad);
    return ()=> img.removeEventListener("load", onLoad);
  }, [fileName]);

  /* 단축키: ← → + - Delete, n, Ctrl+Z */
  useEffect(()=>{
    const onKey=(e)=>{
      if(e.key==="ArrowRight") next();
      if(e.key==="ArrowLeft")  prev();
      if(e.key==="+") setScale(s=>Math.min(5,s+0.1));
      if(e.key==="-") setScale(s=>Math.max(0.2,s-0.1));
      if(e.key==="Delete") delLast();
      if(e.key.toLowerCase()==="n") finalizePolygon();
      if(e.ctrlKey && e.key.toLowerCase()==="z") undo();
    };
    window.addEventListener("keydown", onKey);
    return ()=>window.removeEventListener("keydown", onKey);
  }, [fileName, anns, polyPts, mode]);

  const prev = () => setCurIdx(i=>Math.max(0,i-1));
  const next = () => setCurIdx(i=>Math.min(files.length-1,i+1));

  /* 좌표 변환 */
  const toImgXY = (clientX,clientY) => {
    const r = svgRef.current.getBoundingClientRect();
    const x = (clientX - r.left)/scale;
    const y = (clientY - r.top)/scale;
    return {x:Math.max(0,x), y:Math.max(0,y)};
  };

  /* 마우스 처리 */
  const onMouseDown = (e)=>{
    if(mode==="rect"){
      drawing.current = true;
      startPt.current = toImgXY(e.clientX,e.clientY);
      return;
    }
    // polygon: 점 추가
    const p = toImgXY(e.clientX,e.clientY);
    setPolyPts(ps=>[...ps,p]); setPolyActive(true);
  };

  const onMouseUp = (e)=>{
    if(mode!=="rect" || !drawing.current) return;
    drawing.current=false;
    const end = toImgXY(e.clientX,e.clientY);
    const x = Math.min(startPt.current.x,end.x);
    const y = Math.min(startPt.current.y,end.y);
    const w = Math.abs(end.x-startPt.current.x);
    const h = Math.abs(end.y-startPt.current.y);
    if(!meta || w<2 || h<2) return;
    pushHistory();
    addRect(x,y,w,h);
  };

  /* 추가/삭제/Undo */
  const addRect = (x,y,w,h)=>{
    const area=w*h;
    const newAnn = {
      id: gAnnId++,
      image_id: meta.id,
      category_id: currentCat,
      segmentation: [],
      area,
      bbox: [Number(x.toFixed(2)),Number(y.toFixed(2)),Number(w.toFixed(2)),Number(h.toFixed(2))],
      iscrowd:0,
      attributes:{occluded:false,rotation:0}
    };
    setAnnByImage(p=>({...p,[fileName]:[...(p[fileName]||[]), newAnn]}));
  };

  const addPoly = (flat)=>{
    const xs = flat.filter((_,i)=>i%2===0), ys = flat.filter((_,i)=>i%2===1);
    const x0 = Math.min(...xs), y0 = Math.min(...ys);
    const w  = Math.max(...xs)-x0, h = Math.max(...ys)-y0;
    const area = polyArea(flat);
    const newAnn = {
      id: gAnnId++,
      image_id: meta.id,
      category_id: currentCat,
      segmentation: [flat],
      area,
      bbox: [Number(x0.toFixed(2)),Number(y0.toFixed(2)),Number(w.toFixed(2)),Number(h.toFixed(2))],
      iscrowd:0,
      attributes:{occluded:false,rotation:0}
    };
    setAnnByImage(p=>({...p,[fileName]:[...(p[fileName]||[]), newAnn]}));
  };

  const delLast = ()=>{
    const cur = annByImage[fileName]||[];
    if(!cur.length) return;
    pushHistory();
    setAnnByImage(p=>({...p,[fileName]:cur.slice(0,-1)}));
  };

  const delAt = (i)=>{
    const cur = annByImage[fileName]||[];
    pushHistory();
    const next = cur.slice(); next.splice(i,1);
    setAnnByImage(p=>({...p,[fileName]:next}));
  };

  const pushHistory = ()=>{
    setHistory(h=>{
      const snap = JSON.parse(JSON.stringify(annByImage[fileName]||[]));
      const stack = h[fileName] ? [...h[fileName], snap] : [snap];
      return {...h,[fileName]: stack.slice(-50)};
    });
  };
  const undo = ()=>{
    const stack = history[fileName]||[];
    if(!stack.length) return;
    const prevSnap = stack[stack.length-1];
    setAnnByImage(p=>({...p,[fileName]:prevSnap}));
    setHistory(h=>({...h,[fileName]:stack.slice(0,-1)}));
  };

  /* 폴리곤 완료(N) */
  const finalizePolygon = ()=>{
    if(mode!=="poly" || !meta) return;
    if(polyPts.length<3){ setPolyPts([]); setPolyActive(false); return; }
    pushHistory();
    const flat=[]; for(const p of polyPts){ flat.push(Number(p.x.toFixed(2)), Number(p.y.toFixed(2))); }
    addPoly(flat);
    setPolyPts([]); setPolyActive(false);
  };

  const polyArea = (flat)=>{
    let s=0, n=flat.length/2;
    for(let i=0;i<n;i++){
      const x1=flat[2*i], y1=flat[2*i+1];
      const x2=flat[2*((i+1)%n)], y2=flat[2*((i+1)%n)+1];
      s += x1*y2 - x2*y1;
    }
    return Math.abs(s)/2;
  };

  /* 파일 삭제(좌측 목록) */
  const removeFile = (name)=>{
    const i = files.indexOf(name);
    if(i<0) return;
    const nf = files.filter(f=>f!==name);
    const na = {...annByImage}; delete na[name];
    const nm = {...imagesMeta}; delete nm[name];
    setFiles(nf); setAnnByImage(na); setImagesMeta(nm);
    if(nf.length) setCurIdx(Math.min(i, nf.length-1));
  };

  /* COCO Export + 서버 저장 */
  const save = async ()=>{
    const images = Object.values(imagesMeta).sort((a,b)=>a.id-b.id);
    const annotations=[];
    for(const [fn,list] of Object.entries(annByImage)){
      if(!list) continue;
      for(const a of list) annotations.push(a);
    }
    const coco = {...emptyMeta(projectName), categories, images, annotations};
    if(!annotations.length){ alert("어노테이션이 비어 있습니다."); return; }

    try{
      const r = await fetch("http://127.0.0.1:8000/save",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify(coco)
      });
      const j = await r.json();
      if(j?.detail==="empty payload") alert("서버 본문이 비었습니다. 헤더/본문 확인.");
      else alert("서버 저장 완료");
    }catch(e){ alert("서버 저장 실패: "+e.message); }

    const today = new Date().toISOString().slice(0,10);
    dl(coco, `${projectName}_coco_${today}.json`);
  };

  /* COCO Import: categories/images/annotations 병합 */
  const onImport = async (e)=>{
    const f = e.target.files?.[0]; if(!f) return;
    const text = await f.text();
    const coco = JSON.parse(text);

    // 카테고리 병합(동명이면 유지, 없으면 추가)
    const existNames = new Set(categories.map(c=>c.name));
    let nextCats = [...categories];
    for(const c of (coco.categories||[])){
      if(!existNames.has(c.name)){
        nextCats.push({id: Math.max(0,...nextCats.map(x=>x.id))+1, name:c.name, supercategory:c.supercategory||""});
        existNames.add(c.name);
      }
    }
    setCategories(nextCats);

    // 이미지 메타 주입
    const imMap = {};
    for(const im of (coco.images||[])){
      imMap[im.file_name] = {
        id: im.id, file_name: im.file_name, width: im.width, height: im.height,
        license: im.license||0, flickr_url: im.flickr_url||"", coco_url: im.coco_url||"", date_captured: im.date_captured||0
      };
    }
    setImagesMeta(prev=>({...imMap, ...prev})); // import가 우선

    // 파일 목록 갱신(없는 파일은 스킵되나 메타는 유지)
    const fromJson = (coco.images||[]).map(im=>im.file_name);
    const mergedFiles = Array.from(new Set([...fromJson, ...files]));
    setFiles(mergedFiles);
    if(mergedFiles.length && curIdx>=mergedFiles.length) setCurIdx(0);

    // 어노테이션 주입
    const group = {};
    for(const a of (coco.annotations||[])){
      const im = (coco.images||[]).find(x=>x.id===a.image_id);
      if(!im) continue;
      const fn = im.file_name;
      group[fn] = group[fn] || [];
      // 새로운 ID 채번
      const newAnn = {...a, id: gAnnId++};
      group[fn].push(newAnn);
    }
    setAnnByImage(prev=>({...prev, ...group}));
    alert("COCO JSON Import 완료");
    e.target.value = "";
  };

  /* 렌더 */
  return (
    <div className="w-screen h-screen flex text-sm" style={{fontFamily:"Inter, system-ui, sans-serif"}}>
      {/* 좌측 리스트 */}
      <div className="w-64 border-r overflow-auto bg-[#0f172a] text-white">
        <div className="p-2 flex items-center justify-between">
          <div>Images</div>
          <button className="text-xs border px-2 py-1 rounded" onClick={()=>{setFiles(DEFAULT_FILES); setCurIdx(0);}}>새로고침</button>
        </div>
        {files.map((f,i)=>(
          <div key={f} className={`px-3 py-2 flex items-center justify-between cursor-pointer ${i===curIdx?"bg-[#1e293b]":""}`} onClick={()=>setCurIdx(i)}>
            <span>{f}</span>
            <button className="text-xs bg-[#f43f5e] px-1.5 py-0.5 rounded" onClick={(e)=>{e.stopPropagation(); removeFile(f);}}>X</button>
          </div>
        ))}
      </div>

      {/* 우측 메인 */}
      <div className="flex-1 flex flex-col">
        {/* 상단 바 */}
        <div className="flex items-center gap-2 p-2 border-b">
          <input value={projectName} onChange={e=>setProjectName(e.target.value)} className="border px-2 py-1 rounded" style={{minWidth:240}} placeholder="Project name"/>
          <button className={`border px-2 py-1 rounded ${mode==="rect"?"bg-black text-white":""}`} onClick={()=>setMode("rect")}>Rect (R)</button>
          <button className={`border px-2 py-1 rounded ${mode==="poly"?"bg-black text-white":""}`} onClick={()=>setMode("poly")}>Polygon (P)</button>

          <span className="ml-2">Category</span>
          <select value={currentCat} onChange={e=>setCurrentCat(Number(e.target.value))} className="border px-2 py-1 rounded">
            {categories.map(c=>(
              <option key={c.id} value={c.id}>{c.id}: {c.name}</option>
            ))}
          </select>
          <button className="border px-2 py-1 rounded" onClick={()=>{
            const nid = (categories.length?Math.max(...categories.map(c=>c.id)):0)+1;
            setCategories(cs=>[...cs,{id:nid, name:`class${nid}`, supercategory:""}]);
          }}>+ Add class</button>

          <div className="ml-auto flex items-center gap-2">
            <button className="border px-2 py-1 rounded" onClick={prev}>&laquo;</button>
            <div>{fileName || "-"}</div>
            <button className="border px-2 py-1 rounded" onClick={next}>&raquo;</button>

            <button className="border px-2 py-1 rounded" onClick={()=>setScale(s=>Math.max(0.2,s-0.1))}>-</button>
            <button className="border px-2 py-1 rounded" onClick={()=>setScale(s=>Math.min(5,s+0.1))}>+</button>
            <label>Brightness</label>
            <input type="range" min="50" max="200" value={brightness} onChange={e=>setBrightness(Number(e.target.value))}/>
            <button className="border px-2 py-1 rounded" onClick={()=>{setScale(1); setBrightness(100);}}>Reset</button>

            <button className="border px-2 py-1 rounded" onClick={undo}>Undo</button>
            <button className="border px-2 py-1 rounded" onClick={delLast}>Del last</button>

            {/* Import / Export */}
            <label className="border px-2 py-1 rounded cursor-pointer">
              Import COCO
              <input type="file" accept="application/json" style={{display:"none"}} onChange={onImport}/>
            </label>
            <button className="border px-3 py-1 rounded bg-black text-white" onClick={save}>검토 후 제출(Export COCO)</button>
          </div>
        </div>

        {/* 캔버스 */}
        <div className="flex-1 overflow-auto bg-neutral-100">
          <div style={{position:"relative",width:"fit-content",margin:"18px auto",transform:`scale(${scale})`,transformOrigin:"top left",filter:`brightness(${brightness}%)`}}>
            {fileName && (
              <>
                <img ref={imgRef} src={`${IMAGE_PATH}${fileName}`} alt={fileName} draggable={false} style={{display:"block",userSelect:"none"}}/>
                <svg ref={svgRef} style={{position:"absolute",inset:0,cursor:(mode==="rect"?"crosshair":"pointer")}} onMouseDown={onMouseDown} onMouseUp={onMouseUp}>
                  {/* 기존 어노 */} 
                  {(annByImage[fileName]||[]).map((a,ix)=>{
                    const col = colorOf(a.category_id);
                    if(a.segmentation?.length){ // polygon
                      const pts = a.segmentation[0];
                      const points = pts.map((v,i)=> i%2? "" : `${pts[i]},${pts[i+1]}`).filter(Boolean).join(" ");
                      return (
                        <g key={a.id}>
                          <polygon points={points} fill="none" stroke={col} strokeWidth="2"/>
                          <text x={a.bbox[0]+4} y={a.bbox[1]+14} fontSize="14" fill={col}>
                            {categories.find(c=>c.id===a.category_id)?.name || a.category_id}
                          </text>
                          {/* 박스 개별 삭제 */}
                          <rect x={a.bbox[0]-10} y={a.bbox[1]-10} width="18" height="18" rx="3" fill={col} opacity="0.8" onClick={()=>delAt(ix)}/>
                          <text x={a.bbox[0]-6} y={a.bbox[1]+3} fontSize="14" fill="#fff" style={{pointerEvents:"none"}}>×</text>
                        </g>
                      );
                    }else{ // rect
                      const [x,y,w,h]=a.bbox;
                      return (
                        <g key={a.id}>
                          <rect x={x} y={y} width={w} height={h} fill="none" stroke={col} strokeWidth="2"/>
                          <text x={x+4} y={y+14} fontSize="14" fill={col}>
                            {categories.find(c=>c.id===a.category_id)?.name || a.category_id}
                          </text>
                          <rect x={x-10} y={y-10} width="18" height="18" rx="3" fill={col} opacity="0.8" onClick={()=>delAt(ix)}/>
                          <text x={x-6} y={y+3} fontSize="14" fill="#fff" style={{pointerEvents:"none"}}>×</text>
                        </g>
                      );
                    }
                  })}
                  {/* 진행 중 폴리곤 프리뷰 */}
                  {mode==="poly" && polyPts.length>0 && (
                    <>
                      <polyline points={polyPts.map(p=>`${p.x},${p.y}`).join(" ")} fill="none" stroke={colorOf(currentCat)} strokeWidth="2"/>
                      {polyPts.map((p,i)=>(<circle key={i} cx={p.x} cy={p.y} r="2.5" fill={colorOf(currentCat)}/>))}
                    </>
                  )}
                </svg>
              </>
            )}
          </div>
        </div>

        {/* 하단 도움말 */}
        <div className="p-2 border-t text-neutral-600">
          흐름: 프로젝트명 입력 → Category 선택 → Rect 드래그 또는 Polygon 점 클릭 → <b>N</b>으로 폴리곤 종료 → 좌우로 검토 → 검토 후 제출.  
          단축키: ←/→, +/-, Delete, Ctrl+Z, <b>N</b>(폴리곤 완료).
        </div>
      </div>
    </div>
  );
}
