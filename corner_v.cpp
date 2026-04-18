#include<iostream>
#include<iomanip>
using namespace std;
int main(){
    int n;
    cin>>n;
    for(int i=1;i<=n;i++){
        for(int j=1;j<=n;j++){
            cout<<setw(3)<<min(i,n-j+1);
        }
        cout<<endl;
    }
    return 0;
}