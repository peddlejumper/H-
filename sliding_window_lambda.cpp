#include<iostream>
#include<vector>
#include<deque>
using namespace std;
vector<int>slidingWindow(const vector<int>&a,int k,bool isMax){
    auto process=[&](auto cmp){
        deque<int>q;
        vector<int>r;
        for(int i=0;i<a.size();i++){
            while(!q.empty()&&cmp(a[q.back()],a[i]))q.pop_back();
            q.push_back(i);
            if(q.front()<=i-k)q.pop_front();
            if(i>=k-1)r.push_back(a[q.front()]);
        }
        return r;
    };
    return isMax?process([](int x,int y){return x<=y;}):process([](int x,int y){return x>=y;});
}
int main(){
    int n,k;
    cin>>n>>k;
    vector<int>a(n);
    for(int i=0;i<n;i++)cin>>a[i];
    vector<int>minV=slidingWindow(a,k,false);
    vector<int>maxV=slidingWindow(a,k,true);
    for(int i=0;i<minV.size();i++){
        if(i>0)cout<<" ";
        cout<<minV[i];
    }
    cout<<endl;
    for(int i=0;i<maxV.size();i++){
        if(i>0)cout<<" ";
        cout<<maxV[i];
    }
    cout<<endl;
    return 0;
}