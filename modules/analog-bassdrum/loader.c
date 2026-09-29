/* Part-scoped DSP packages streamed in the spare portion of stock FLEX
 * records. This runs only in the source builder, never the UI thread.
 * Firmware library is immutable, checked by the preboot loader's hash.
 */
#include <stdint.h>
#define LIB ((const uint32_t *)0x40c00000u)
#define MAX_ENGINES 4
#define P_ORG 0x2000u
#define X_ORG 0x4000u
#define X_DATA 0x2b40u
#define X_STATE 0x3700u
#define X_META 0x3800u
#define CHUNK 16u
struct entry { uint32_t id,pn,xn,code[2],data,pr,prn,xr,xrn,initial,entry; };
struct loaded { const struct entry *e; uint32_t p,x; };
struct plan {
    struct loaded engines[MAX_ENGINES];
    uint32_t entries[4],models[4],pending[4],count,stage,engine,offset,sequence,sum,error;
};
static struct plan plans[2]={0};
static uint32_t old_bank=0, old_part=0, old_models[8]={0};
uint32_t ab_load_error=0, ab_load_generation=0, ab_load_packets=0;
static const struct entry *entry(unsigned id) {
    if(LIB[0]!=0x41424c31u || LIB[1]!=1 || LIB[2]>0x100000u || LIB[3]>128 || id>=LIB[3]) return 0;
    return (const struct entry *)(LIB+16+12*id);
}
static void refresh(const volatile uint8_t *part,uint32_t bank,unsigned partidx) {
    uint32_t models[8]; unsigned changed=bank!=old_bank || partidx!=old_part;
    for(unsigned t=0;t<8;++t) {
        const volatile uint8_t *s=part+60+30*t;
        models[t]=(part[0x22+t]==1 && s[0]=='A' && s[1]=='B' && s[2]==1)?part[0x1da+6+30*t]:0xffffffffu;
        if(models[t]!=old_models[t]) changed=1;
    }
    if(!changed) return;
    old_bank=bank;old_part=partidx;++ab_load_generation;ab_load_error=0;
    for(unsigned t=0;t<8;++t) old_models[t]=models[t];
    for(unsigned c=0;c<2;++c) {
        struct plan *p=plans+c;
        p->count=p->stage=p->engine=p->offset=p->sequence=p->sum=p->error=0;
        unsigned pc=LIB[4+2*c],xc=X_DATA;
        for(unsigned t=0;t<4;++t) {
            unsigned id=models[(c?0:4)+t];p->models[t]=id;p->entries[t]=0;p->pending[t]=0;
            if(id==0xffffffffu) continue;
            const struct entry *e=entry(id);
            if(!e) {p->error=1;continue;}
            unsigned i=0; for(;i<p->count;++i) if(p->engines[i].e==e) break;
            if(i==p->count) {
                if(e->pn>LIB[5+2*c]-pc || e->xn>X_STATE-xc) {p->error=1;continue;}
                p->engines[i].e=e;p->engines[i].p=pc;p->engines[i].x=xc;++p->count;
                pc+=e->pn;xc+=e->xn;
            }
            p->entries[t]=p->engines[i].p+e->entry;
        }
        ab_load_error|=p->error<<c;
    }
}
static void header(struct plan *p,volatile uint32_t *r,unsigned cmd,unsigned dst,unsigned n) {
    r[2]=(cmd<<16)|n;r[3]=(dst<<16)|p->sequence++;
    ++ab_load_packets;
}
static unsigned relocated(const struct loaded *l,unsigned core,unsigned at) {
    const struct entry *e=l->e;unsigned v=LIB[e->code[core]+at];
    for(unsigned i=0;i<e->prn;++i) if(LIB[e->pr+i]==at) v+=l->p-P_ORG;
    for(unsigned i=0;i<e->xrn;++i) if(LIB[e->xr+i]==at) v+=l->x-X_ORG;
    return v&0xffffffu;
}
static void pending(struct plan *p,unsigned track,volatile uint32_t *r) {
    if(p->stage==6 && !p->error && p->pending[track&3]) {
        r[1]=(r[1]&0xffff0000u)|2u;p->pending[track&3]=0;
    }
}
void ab_load_record(const volatile uint8_t *part,uint32_t bank,unsigned partidx,unsigned track,volatile uint32_t *r) {
    refresh(part,bank,partidx);
    unsigned core=track<4?1:0;struct plan *p=plans+core;
    if(p->stage<6 && (r[1]&1)) {p->pending[track&3]=1;r[1]&=~1u;}
    pending(p,track,r);
    unsigned cmd=2,dst=0,n=0;
    if(p->stage==0) {header(p,r,3,0,0);p->stage=p->error?6:1;return;}
    while(p->stage==1 || p->stage==2) {
        if(p->engine==p->count) {++p->stage;p->engine=p->offset=0;continue;}
        const struct loaded *l=p->engines+p->engine;const struct entry *e=l->e;
        unsigned total=p->stage==1?e->pn:e->xn;
        if(p->offset==total) {++p->engine;p->offset=0;continue;}
        n=total-p->offset;if(n>CHUNK)n=CHUNK;
        cmd=p->stage==1?1:2;dst=(cmd==1?l->p:l->x)+p->offset;
        for(unsigned i=0;i<n;++i) r[10+i]=cmd==1?relocated(l,core,p->offset+i):LIB[e->data+p->offset+i];
        p->offset+=n;break;
    }
    if(!n && p->stage==3) {
        if(p->offset==256) {++p->stage;p->offset=0;}
        else {
            n=CHUNK;dst=X_STATE+p->offset;
            unsigned t=p->offset/64;const struct entry *e=entry(p->models[t]);
            for(unsigned i=0;i<n;++i) r[10+i]=e?LIB[e->initial+p->offset%64+i]:0;
            p->offset+=n;
        }
    }
    if(!n && p->stage==4) {n=4;dst=X_META;for(unsigned i=0;i<n;++i)r[10+i]=p->entries[i];++p->stage;}
    if(!n && p->stage==5) {r[10]=p->sum;header(p,r,4,0,0);p->stage=6;pending(p,track,r);return;}
    if(n) {
        p->sum=(p->sum+cmd+dst+n+p->sequence)&0xffffffu;
        for(unsigned i=0;i<n;++i)p->sum=(p->sum+r[10+i])&0xffffffu;
        header(p,r,cmd,dst,n);
    }
}
