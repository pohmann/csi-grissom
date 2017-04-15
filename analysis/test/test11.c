int main(int argc, char** argv){
  if(argc < 4){ //entry
    argc++; //A
    if(argc < 3) //B
      goto crash; //not in picture; edge B->crash
    argc--; // X
  }
  argc+=2; //C
  argc+=3; //D
crash:
  argc-=5;
}
