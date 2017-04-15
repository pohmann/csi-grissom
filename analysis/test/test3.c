int main(int argc, char** argv){
  int x = atoi(argv[1]);
  int y = atoi(argv[2]);
  if(x < y){
    x++;
    while(x < y){
      x++;
    }
  }
  printf("%d %d\n", x, y);
}
