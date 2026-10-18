"""Compact, persistent N1800 delivery notification and multi-target status page."""
import time
import tkinter as tk

BG="#101927"
PANEL="#192738"
FG="#f1f5fb"
MUTED="#a8bacd"
GREEN="#52c39b"
WARN="#f4bc71"
BAD="#fa8e8e"

LABELS={
    "queued":"Wartet auf Übertragung",
    "retry":"Neuer Versuch geplant",
    "sending":"Wird zugestellt",
    "done":"An Ziel übergeben",
    "review":"Übertragung unklar: am Ziel prüfen",
    "failed":"Fehlgeschlagen",
}

class DeliveryStatusPage:
    def __init__(self,root,queue,back,owner=None):
        self.root=root
        self.queue=queue
        self.back=back
        self.owner=owner
        self.frame=None
        self.focus_id=None
        self.refresh_id=None
        self.items=None

    def _button(self,parent,text,callback):
        return tk.Button(parent,text=text,command=callback,bg=PANEL,fg=FG,
                         activebackground="#397edb",activeforeground=FG,
                         relief="flat",bd=0,font=("DejaVu Sans",13),
                         cursor="none",padx=14,pady=9)

    def show(self,focus_batch=None,owner=None):
        self.hide()
        self.owner=owner
        self.focus_id=focus_batch
        self.frame=tk.Frame(self.root,bg=BG)
        self.frame.place(x=0,y=0,relwidth=1,relheight=1)
        self.frame.lift()
        header=tk.Frame(self.frame,bg=BG)
        header.pack(fill="x",padx=30,pady=(18,8))
        tk.Label(header,text="Meldungen & Aufträge",font=("DejaVu Sans",22,"bold"),
                 bg=BG,fg=FG).pack(side="left")
        self._button(header,"← Zurück",self.close).pack(side="right")
        area=tk.Frame(self.frame,bg=BG)
        area.pack(fill="both",expand=True,padx=24,pady=8)
        canvas=tk.Canvas(area,highlightthickness=0,bg=BG)
        scroller=tk.Scrollbar(area,command=canvas.yview,width=22)
        scroller.pack(side="right",fill="y")
        canvas.pack(side="left",fill="both",expand=True)
        canvas.configure(yscrollcommand=scroller.set)
        content=tk.Frame(canvas,bg=BG)
        window=canvas.create_window((0,0),anchor="nw",window=content)
        content.bind("<Configure>",lambda _e:canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e:canvas.itemconfigure(window,width=e.width))
        canvas.bind("<MouseWheel>",lambda e:canvas.yview_scroll(
            -1 if e.delta>0 else 1,"units"))
        self.items=content
        self._refresh()

    def _refresh(self):
        if self.frame is None or not self.frame.winfo_exists():
            return
        for widget in self.items.winfo_children():
            widget.destroy()
        groups=self.queue.recent_batches(35)
        groups=[g for g in groups if self.owner is None or
                g["batch"]["owner_id"] == self.owner]
        if self.focus_id:
            groups.sort(key=lambda x:x["batch"]["id"]!=self.focus_id)
        if not groups:
            tk.Label(self.items,text="Noch keine Meldungen",bg=BG,fg=MUTED,
                     font=("DejaVu Sans",16)).pack(pady=30)
        for group in groups:
            batch=group["batch"]
            jobs=group["jobs"]
            card=tk.Frame(self.items,bg=PANEL)
            card.pack(fill="x",padx=5,pady=7)
            remaining=sum(j["status"] in ("queued","sending","retry") for j in jobs)
            problems=sum(j["status"] in ("failed","review") for j in jobs)
            successes=sum(j["status"]=="done" for j in jobs)
            status=f"{successes} von {len(jobs)} Zielen übergeben"
            color=BAD if problems else WARN if remaining else GREEN
            tk.Label(card,text=batch["label"]+"  ·  "+
                     time.strftime("%d.%m. %H:%M",time.localtime(batch["created_at"])),
                     bg=PANEL,fg=FG,font=("DejaVu Sans",13,"bold"),
                     anchor="w").pack(fill="x",padx=14,pady=(10,2))
            tk.Label(card,text=status,bg=PANEL,fg=color,anchor="w",
                     font=("DejaVu Sans",11)).pack(fill="x",padx=14,pady=(0,5))
            for j in jobs:
                description=LABELS.get(j["status"],j["status"])
                extra=(" · "+j["last_error"][:100]) if j["last_error"] else ""
                tk.Label(card,text=j["target_name"]+" · "+description+extra,
                         bg=PANEL,fg=BAD if j["status"] in ("failed","review") else MUTED,
                         anchor="w",justify="left",wraplength=830,
                         font=("DejaVu Sans",11)).pack(fill="x",padx=16,pady=2)
            if not batch["read_at"]:
                self._button(card,"Als gelesen markieren",
                             lambda bid=batch["id"]:self._read(bid)).pack(
                                 anchor="e",padx=10,pady=6)
        self.refresh_id=self.root.after(2500,self._refresh)

    def _read(self,batch_id):
        self.queue.mark_batch_read(batch_id)
        self._refresh()

    def close(self):
        self.hide()
        self.back()

    def hide(self):
        if self.refresh_id is not None:
            try:self.root.after_cancel(self.refresh_id)
            except tk.TclError:pass
            self.refresh_id=None
        if self.frame is not None:
            self.frame.destroy()
            self.frame=None
