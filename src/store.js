import { create } from "zustand";

export const useLabStore = create((set, get)=>({
  image: null,
  anns: [],
  history: [],
  index: -1,
  setImage: (img)=> set({ image: img, anns: [], history: [], index: -1 }),
  loadAnns: (arr)=> set({ anns: arr, history: [], index: -1 }),
  snapshot(){ // 내부용
    const snap = JSON.parse(JSON.stringify(get().anns));
    const h = get().history.slice(0, get().index+1).concat([snap]);
    set({ history: h, index: h.length-1 });
  },
  undo(){ const { history, index } = get();
    if(index>=0) set({ anns: JSON.parse(JSON.stringify(history[index])), index:index-1 }); },
  redo(){ const { history, index } = get();
    if(index < history.length-1)
      set({ anns: JSON.parse(JSON.stringify(history[index+1])), index:index+1 }); },
  addBBox(bbox){
    const { image, anns } = get();
    const n = anns.concat([{ id:null, image_id:image.id, atype:"bbox", label:"object", bbox }]);
    set({ anns: n }); get().snapshot();
  },
  updateBBox(i, bbox){
    const arr = [...get().anns]; arr[i] = { ...arr[i], bbox }; set({ anns: arr });
  }
}));
