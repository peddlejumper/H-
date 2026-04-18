#include<iostream>
#include<vector>
#include<deque>
using namespace std;
vector<int>getMinValues(const vector<int>&arr,int k){
    deque<int>q;
    vector<int>result;
    for(int i=0;i<arr.size();i++){
        while(!q.empty()&&arr[q.back()]>=arr[i])q.pop_back();
        q.push_back(i);
        if(q.front()<=i-k)q.pop_front();
        if(i>=k-1)result.push_back(arr[q.front()]);
    }
    return result;
}
vector<int>getMaxValues(const vector<int>&arr,int k){
    deque<int>q;
    vector<int>result;
    for(int i=0;i<arr.size();i++){
        while(!q.empty()&&arr[q.back()]<=arr[i])q.pop_back();
        q.push_back(i);
        if(q.front()<=i-k)q.pop_front();
        if(i>=k-1)result.push_back(arr[q.front()]);
    }
    return result;
}
int main(){
    int n,k;
    cin>>n>>k;
    vector<int>arr(n);
    for(int i=0;i<n;i++)cin>>arr[i];
    vector<int>minVals=getMinValues(arr,k);
    vector<int>maxVals=getMaxValues(arr,k);
    for(int i=0;i<minVals.size();i++){
        if(i>0)cout<<" ";
        cout<<minVals[i];
    }
    cout<<endl;
    for(int i=0;i<maxVals.size();i++){
        if(i>0)cout<<" ";
        cout<<maxVals[i];
    }
    cout<<endl;
    return 0;
}